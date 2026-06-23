#!/usr/bin/env python3
"""
scripts/run_phase2_search_stepstone.py

Phase 2B (Stepstone): 搜索所有 group 的 primary keywords，
通过 Stepstone MCP HTTP SSE 服务抓取职缺详情，
最终保存为 output/temp/_phase2_temp_stepstone.json。

前提：
  1. 已安装 mcp Python SDK：pip install mcp
  2. Stepstone MCP server 正在运行：python -m stepstone_http_server
     (默认监听 http://127.0.0.1:8000/mcp)

用法：
  python3 scripts/run_phase2_search_stepstone.py
  python3 scripts/run_phase2_search_stepstone.py --config config.json
"""

import asyncio
import random
import hashlib
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from search_state import load_cv_skills, quick_score, init_paths

# Fix Windows GBK crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

OUTPUT_DIR:  Path = None  # type: ignore  # set in main()
TEMP_DIR:    Path = None  # type: ignore
CONFIG_PATH: Path = None  # type: ignore


# ─── Stable job ID ────────────────────────────────────────────────────────────

def _extract_posted_days_ago(text: str) -> "int | None":
    """
    Parse German relative-date phrases from Stepstone page text.
    Returns days-ago as int, or None if no pattern found.
    """
    lower = text.lower()
    m = re.search(r"vor\s+(\d+)\s+tag", lower)
    if m:
        return int(m.group(1))
    if "vor einem tag" in lower:
        return 1
    m = re.search(r"vor\s+(\d+)\s+woche", lower)
    if m:
        return int(m.group(1)) * 7
    if "vor einer woche" in lower:
        return 7
    if re.search(r"vor\s+\d+\s+stunde", lower) or "vor einer stunde" in lower:
        return 0
    if "heute" in lower:
        return 0
    if "gestern" in lower:
        return 1
    return None


def make_stepstone_job_id(url: str, fallback_seed: str = "") -> str:
    """Generate stable ID: st_ + first 16 hex chars of SHA256(url).
    16 hex = 64-bit space → collision threshold ~4B entries (vs 65K for MD5[:8]).
    """
    seed = url if url else fallback_seed
    return "st_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _title_from_stepstone_url(url: str) -> str:
    """Best-effort title from Stepstone URL slug. Returns '' if URL doesn't match."""
    m = re.search(r"stellenangebote--(.+?)--\d+-inline\.html", url, re.IGNORECASE)
    if not m:
        return ""
    slug = m.group(1).replace("-", " ")
    slug = re.sub(r"\b(m w d|f m x|all genders)\b", "", slug, flags=re.IGNORECASE)
    return slug.strip()


# ─── Response parsers ─────────────────────────────────────────────────────────

def parse_search_response(text: str) -> tuple[str, int, list[dict]]:
    """
    Parse search_jobs text response → (session_id, job_count, job_list).
    Handles both old format (Found N jobs / job_index 0-N) and new format
    (Total Jobs Found: N / numbered list with Link: entries).
    """
    session_id = ""
    job_count  = 0
    job_list: list[dict] = []
    current_job: dict | None = None

    for line in text.splitlines():
        stripped = line.strip()
        lower    = stripped.lower()

        # Session ID
        if lower.startswith("session id:") or lower.startswith("session_id:"):
            session_id = stripped.split(":", 1)[1].strip()

        # "Total Jobs Found: 25" (new format)
        m_total = re.search(r"total jobs found:\s*(\d+)", stripped, re.IGNORECASE)
        if m_total:
            job_count = int(m_total.group(1))

        # "Found N jobs" (old format) — only if not already set
        if not job_count:
            m_found = re.search(r"(\d+)\s+job", stripped, re.IGNORECASE)
            if m_found:
                job_count = int(m_found.group(1))

        # "job_index 0-N" (old format)
        m_idx = re.search(r"job_index\s+\d+[-–](\d+)", stripped, re.IGNORECASE)
        if m_idx:
            job_count = int(m_idx.group(1)) + 1

        # Numbered job entry: "1. Title of Job"
        m_num = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if m_num:
            current_job = {"title": m_num.group(2).strip(), "url": ""}
            job_list.append(current_job)

        # URL line under a numbered entry
        if stripped.startswith("Link:") and current_job is not None:
            url_val = stripped[len("Link:"):].strip()
            current_job["url"] = url_val

    return session_id, job_count, job_list


def parse_job_details_response(text: str) -> dict:
    """
    Parse get_job_details text response into structured fields.

    MCP server format (current):
      📋 Job Details: <title>
      🏢 Company: <company>
      📍 Location: <location>
      💰 Salary: <salary value>       ← optional single line
      📝 Description:\n<desc text>
      ✅ Requirements:\n  • <item>...
      🛠 Responsibilities:\n  • <item>...
      🎁 Benefits:\n  • <item>...

    Legacy format:
      title: / company: / location: / url: plain-text keys
      💰 Salary: <entire page blob> (old behaviour — kept for back-compat)
    """
    fields: dict[str, str] = {}

    # Single-line emoji fields
    SINGLE_LINE = {
        "📋 job details:": "title",
        "🏢 company:":     "company",
        "📍 location:":    "location",
        "💰 salary:":      "_salary_line",
        "⏰ employment type:": "_employment_type",
        "🧠 experience level:": "_experience_level",
        "📅 posted:":      "_posted",
    }
    # Multi-line section headers — everything after the header line until the
    # next section header is the section body.
    SECTION_HEADERS = {
        "📝 description:":   "desc",
        "✅ requirements:":  "reqs",
        "🛠 responsibilities:": "resp",
        "🎁 benefits:":      "bens",
        "🏢 company profile:": "company_profile",
    }

    sections: dict[str, list[str]] = {k: [] for k in SECTION_HEADERS.values()}
    current_section: "str | None" = None
    salary_blob = ""  # legacy: full-blob after 💰 Salary line

    for line in text.splitlines():
        stripped = line.strip()
        lower    = stripped.lower()

        # Check section header
        matched_section = False
        for prefix, key in SECTION_HEADERS.items():
            if lower.startswith(prefix):
                current_section = key
                # content after the colon on the same line (if any)
                rest = stripped[len(prefix):].strip()
                if rest:
                    sections[key].append(rest)
                matched_section = True
                break
        if matched_section:
            continue

        # Accumulate into active section
        if current_section is not None:
            if stripped:
                sections[current_section].append(stripped)
            continue

        # Single-line emoji fields
        matched_field = False
        for prefix, key in SINGLE_LINE.items():
            if lower.startswith(prefix):
                value = stripped[len(prefix):].strip()
                fields[key] = value
                if key == "_salary_line":
                    salary_blob = value  # legacy compat
                matched_field = True
                break
        if matched_field:
            continue

        # Old plain-text format
        for key in ("title", "company", "location"):
            if lower.startswith(f"{key}:"):
                fields[key] = stripped.split(":", 1)[1].strip()
                break
        if lower.startswith("job url:") or lower.startswith("url:"):
            raw_url = stripped.split(":", 1)[1].strip()
            if raw_url.startswith("//"):
                raw_url = "https:" + raw_url
            fields["url"] = raw_url

    # ── Build description_full ────────────────────────────────────────────────
    desc_full = ""

    # Priority 1: 📝 Description section (current MCP format)
    desc_lines = sections.get("desc", [])
    if desc_lines:
        desc_parts = ["\n".join(desc_lines)]
        reqs = sections.get("reqs", [])
        if reqs:
            desc_parts.append("Requirements:\n" + "\n".join(reqs))
        resp = sections.get("resp", [])
        if resp:
            desc_parts.append("Responsibilities:\n" + "\n".join(resp))
        bens = sections.get("bens", [])
        if bens:
            desc_parts.append("Benefits:\n" + "\n".join(bens))
        desc_full = "\n\n".join(desc_parts)

    # Priority 2: legacy salary-blob approach (old MCP format)
    if not desc_full and salary_blob:
        SALARY_TRIGGERS = ["Gehalt anzeigen", "Gehalt einblenden", "Salary"]
        trigger_found = next((t for t in SALARY_TRIGGERS if t in salary_blob), None)
        if trigger_found:
            after = salary_blob.split(trigger_found, 1)[1].strip()
            title   = fields.get("title", "")
            company = fields.get("company", "")
            prefix_str = (title + company)[:120]
            if after.startswith(prefix_str[:40]):
                after = after[len(prefix_str):].lstrip()
            desc_full = after
        else:
            desc_full = salary_blob

    # ── Title / company override from section data if single-line was empty ───
    if not fields.get("title"):
        fields["title"] = fields.get("title", "")
    if not fields.get("company"):
        cp_lines = sections.get("company_profile", [])
        if cp_lines:
            fields["company"] = cp_lines[0]

    # Best-effort posting date
    raw_date_text = salary_blob or desc_full
    days_ago = _extract_posted_days_ago(raw_date_text)
    if not days_ago and fields.get("_posted"):
        days_ago = _extract_posted_days_ago(fields["_posted"])
    posted_at = (date.today() - timedelta(days=days_ago)).isoformat() if days_ago is not None else None

    return {
        "title":               fields.get("title",   ""),
        "company":             fields.get("company", ""),
        "location":            fields.get("location",""),
        "url":                 fields.get("url",     ""),
        "salary":              fields.get("_salary_line", ""),
        "posted_at":           posted_at,
        "description_full":    desc_full,
        "description_snippet": desc_full[:800],
    }


# ─── Async MCP session ────────────────────────────────────────────────────────

_DETAIL_BATCH_SIZE = 5  # max get_job_details calls per session before refreshing


async def search_group_zip(
    group: dict,
    zip_entry: dict,
    stepstone_cfg: dict,
    keyword_list: list[str] | None = None,
    keyword_type: str = "primary",
) -> list[dict]:
    """
    Search all keywords for a group at one zip_code, then fetch details.
    Opens a fresh MCP session every _DETAIL_BATCH_SIZE jobs to avoid
    the server-side session staleness limit (~8 fetches per session).
    Returns list of unified-schema job dicts.
    """
    try:
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession
    except ImportError:
        print("[ERROR] mcp package not installed. Run: pip install mcp", file=sys.stderr)
        return []

    server_url  = stepstone_cfg.get("server_url", "http://127.0.0.1:8000/mcp")
    radius      = stepstone_cfg.get("radius_km", 50)
    max_jobs    = stepstone_cfg.get("max_jobs_per_group", 20)
    zip_code    = zip_entry["zip"]
    zip_label   = zip_entry.get("label", zip_code)
    gid         = group["group_id"]
    glabel      = group.get("group_label", gid)

    if keyword_list is not None:
        keywords = keyword_list
    else:
        seen_kws: set[str] = set()
        keywords: list[str] = []
        for lang_kws in group["primary_keywords"].values():
            for kw in lang_kws:
                if kw not in seen_kws:
                    seen_kws.add(kw)
                    keywords.append(kw)

    search_args = {"search_terms": keywords, "zip_code": zip_code, "radius": radius}

    # ── Phase 1: initial search → collect full job_list (titles + URLs) ───────
    session_id_initial = ""
    job_count  = 0
    job_list: list[dict] = []

    try:
        async with streamablehttp_client(server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                # Dynamic timeout: each keyword takes up to ~13.5s (HTTP + sleep)
                search_timeout = len(keywords) * 13.5 + 20.0
                try:
                    search_result = await asyncio.wait_for(
                        session.call_tool("search_jobs", search_args), timeout=search_timeout)
                except asyncio.TimeoutError:
                    print(f"  [WARN] Stepstone search_jobs timeout for {glabel} @ {zip_label}",
                          file=sys.stderr)
                    return []
                search_text = search_result.content[0].text or "" if search_result.content else ""
                session_id_initial, job_count, job_list = parse_search_response(search_text)
    except Exception as e:
        print(f"  [ERROR] Stepstone initial search failed for {glabel} @ {zip_label}: {e}",
              file=sys.stderr)
        return []

    if not session_id_initial or job_count == 0:
        print(f"  [WARN] Stepstone: no results for {glabel} @ {zip_label}", file=sys.stderr)
        return []

    if not job_list:
        job_list = [{"title": f"job_{i}", "url": ""} for i in range(job_count)]

    fetch_count = min(len(job_list), max_jobs)
    n_batches   = (fetch_count + _DETAIL_BATCH_SIZE - 1) // _DETAIL_BATCH_SIZE
    print(f"  Stepstone {glabel} @ {zip_label}: "
          f"session={session_id_initial[:8]}... found={job_count}, "
          f"fetching={fetch_count} ({n_batches} batch{'es' if n_batches != 1 else ''})")

    results: list[dict] = []

    # ── Phase 2: fetch details — reuse session_id_initial to avoid extra search_jobs calls
    # (extra calls trigger Stepstone rate-limiting and return 0 results)
    for batch_start in range(0, fetch_count, _DETAIL_BATCH_SIZE):
        batch = job_list[batch_start:batch_start + _DETAIL_BATCH_SIZE]

        try:
            async with streamablehttp_client(server_url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # Reuse session_id_initial — avoids re-running search_jobs which
                    # gets rate-limited after the first call.
                    fresh_id = session_id_initial

                    for batch_idx, job_meta in enumerate(batch):
                        global_idx = batch_start + batch_idx
                        try:
                            detail_result = await asyncio.wait_for(
                                session.call_tool("get_job_details", {
                                    "job_query":  job_meta["title"],
                                    "session_id": fresh_id,
                                }),
                                timeout=60.0,
                            )
                        except asyncio.TimeoutError:
                            print(f"  [WARN] get_job_details timeout idx={global_idx} @ {zip_label}",
                                  file=sys.stderr)
                            continue

                        detail_text = detail_result.content[0].text or "" if detail_result.content else ""
                        parsed  = parse_job_details_response(detail_text)
                        job_url = job_meta.get("url") or parsed.get("url", "")
                        job_id  = make_stepstone_job_id(job_url, f"{fresh_id}_{global_idx}")

                        # 3-tier title recovery when get_job_details returns empty
                        if not parsed["title"]:
                            parsed["title"] = (
                                job_meta.get("title", "")             # tier 1: search-results list
                                or _title_from_stepstone_url(job_url) # tier 2: URL slug
                            )

                        job: dict = {
                            "job_id":              job_id,
                            "title":               parsed["title"],
                            "company":             parsed["company"],
                            "location":            parsed["location"],
                            "posted_at":           None,
                            "description_snippet": parsed["description_snippet"],
                            "description_full":    parsed["description_full"],
                            "url":                 job_url,
                            "_keyword":            "; ".join(keywords[:3]),
                            "_keyword_type":       keyword_type,
                            "_group_id":           gid,
                            "_group_label":        glabel,
                            "_source":             "stepstone",
                            "_zip_code":           zip_code,
                            "_zip_label":          zip_label,
                            "_salary":             parsed.get("salary", ""),
                            "_needs_refetch":      not bool(parsed["description_full"]),
                        }
                        results.append(job)
                        print(f"    [{global_idx+1}/{fetch_count}] {job_id}: "
                              f"{job['title'][:50]} @ {job['company'][:25]}")

        except asyncio.TimeoutError:
            print(f"  [ERROR] Stepstone batch (start={batch_start}) timed out @ {zip_label}",
                  file=sys.stderr)
        except Exception as e:
            print(f"  [ERROR] Stepstone batch (start={batch_start}) failed @ {zip_label}: {e}",
                  file=sys.stderr)

    return results


async def run_all(config: dict, group_id: str | None = None) -> list[dict]:
    """Run searches for all groups × zip_codes sequentially."""
    stepstone_cfg = config.get("stepstone", {})
    zip_codes     = stepstone_cfg.get("zip_codes", [])
    groups        = config["job_search"]["keyword_groups"]

    if group_id:
        groups = [g for g in groups if g["group_id"] == group_id]
        if not groups:
            print(f"[ERROR] group_id '{group_id}' not found in config", file=sys.stderr)
            return []

    FALLBACK_THRESHOLD = 5
    SCORE_THRESHOLD    = 50

    all_jobs: list[dict] = []

    for group in groups:
        gid            = group.get("group_id", "?")
        group_job_ids: set[str] = set()
        group_jobs:    list[dict] = []
        cv_skills = load_cv_skills(str(OUTPUT_DIR / f"cv_parsed_{gid}.json"))

        # ── Phase A: primary keywords across all zip codes ───────────────────
        for zip_entry in zip_codes:
            try:
                jobs = await asyncio.wait_for(
                    search_group_zip(group, zip_entry, stepstone_cfg,
                                     keyword_type="primary"),
                    timeout=600.0,
                )
            except asyncio.TimeoutError:
                print(f"  [ERROR] search_group_zip timeout for {gid} @ {zip_entry.get('label')}",
                      file=sys.stderr)
                jobs = []
            for j in jobs:
                if j["job_id"] not in group_job_ids:
                    group_job_ids.add(j["job_id"])
                    group_jobs.append(j)
            await asyncio.sleep(random.uniform(3.0, 5.0))

        high_score_count = sum(1 for j in group_jobs if quick_score(j, cv_skills) > SCORE_THRESHOLD)
        print(f"  Group {gid}: {high_score_count} jobs with score > {SCORE_THRESHOLD}")

        # ── Phase B: fallback to job_family (all language keys) ─────────────
        if high_score_count < FALLBACK_THRESHOLD:
            fb_keywords = list(dict.fromkeys(
                kw for lang_kws in group.get("job_family", {}).values()
                for kw in lang_kws
            ))
            print(f"  [FALLBACK] {gid}: {high_score_count} < {FALLBACK_THRESHOLD} → "
                  f"searching {len(fb_keywords)} job_family keywords")

            for zip_entry in zip_codes:
                try:
                    jobs = await asyncio.wait_for(
                        search_group_zip(group, zip_entry, stepstone_cfg,
                                         keyword_list=fb_keywords,
                                         keyword_type="fallback"),
                        timeout=600.0,
                    )
                except asyncio.TimeoutError:
                    print(f"  [ERROR] fallback timeout for {gid} @ {zip_entry.get('label')}",
                          file=sys.stderr)
                    jobs = []
                for j in jobs:
                    if j["job_id"] not in group_job_ids:
                        group_job_ids.add(j["job_id"])
                        group_jobs.append(j)
                await asyncio.sleep(random.uniform(3.0, 5.0))

        all_jobs.extend(group_jobs)

    return all_jobs


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global OUTPUT_DIR, TEMP_DIR, CONFIG_PATH
    import argparse
    parser = argparse.ArgumentParser(description="Stepstone Phase 2B search")
    parser.add_argument("--uid",    default="leon", help="用户 ID（对应 users/{uid}/ 目录）")
    parser.add_argument("--config", default=None,   help="覆盖 config.json 路径")
    parser.add_argument("--group",  default=None,   help="Filter by group_id (e.g. group-da)")
    args = parser.parse_args()

    _base       = Path(__file__).resolve().parent.parent / "users" / args.uid
    OUTPUT_DIR  = _base / "output"
    TEMP_DIR    = OUTPUT_DIR / "temp"
    CONFIG_PATH = _base / "config.json"
    init_paths(args.uid)

    config_path = Path(args.config) if args.config else CONFIG_PATH
    if not config_path.exists():
        print(f"[ERROR] config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    stepstone_cfg = config.get("stepstone", {})

    if not stepstone_cfg.get("enabled", False):
        print("Stepstone disabled in config (stepstone.enabled=false), skipping.")
        print(json.dumps({"fetched_total": 0, "temp_file": ""}))
        return

    print("=" * 60)
    print("Phase 2B: Stepstone search")
    print(f"  zip_codes: {[z['label'] for z in stepstone_cfg.get('zip_codes', [])]}")
    print(f"  radius_km: {stepstone_cfg.get('radius_km', 50)}")
    print(f"  max_jobs_per_group: {stepstone_cfg.get('max_jobs_per_group', 20)}")
    print("=" * 60)

    all_jobs = asyncio.run(run_all(config, group_id=args.group))

    # Deduplicate within this run by job_id
    seen: set[str] = set()
    unique_jobs: list[dict] = []
    for job in all_jobs:
        if job["job_id"] not in seen:
            seen.add(job["job_id"])
            unique_jobs.append(job)

    # B1: Filter by date_range_days when posted_at is available
    date_range = config["job_search"].get("date_range_days", 14)
    cutoff = date.today() - timedelta(days=date_range)
    dated   = [j for j in unique_jobs if j.get("posted_at") is not None]
    undated = [j for j in unique_jobs if j.get("posted_at") is None]
    fresh   = [j for j in dated if j["posted_at"] >= cutoff.isoformat()]
    if dated:
        print(f"  Date filter ({date_range}d): {len(dated)} dated → {len(fresh)} fresh, "
              f"{len(dated)-len(fresh)} filtered out, {len(undated)} undated (kept)")
    unique_jobs = fresh + undated

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = TEMP_DIR / "_phase2_temp_stepstone.json"
    temp_path.write_text(
        json.dumps(unique_jobs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nSaved {len(unique_jobs)} Stepstone jobs to {temp_path}")
    print(json.dumps({
        "fetched_total": len(unique_jobs),
        "temp_file":     str(temp_path),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
