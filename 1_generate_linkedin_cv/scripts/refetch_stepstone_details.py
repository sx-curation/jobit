#!/usr/bin/env python3
"""
scripts/refetch_stepstone_details.py

Re-fetches Stepstone job details for empty-description jobs in an existing batch.

Modes:
  --mode mcp  (default) — uses Stepstone MCP with fresh sessions per 5 jobs.
                          Works even with anti-bot protection.
  --mode http           — direct HTTP GET (fails if Stepstone blocks urllib).

Usage:
  python3 scripts/refetch_stepstone_details.py --batch-id 20260607_002 --uid leon
  python3 scripts/refetch_stepstone_details.py --batch-id 20260607_002 --uid leon --mode http
"""

import argparse
import asyncio
import html as _html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search_state as _ss
from run_phase2_search_stepstone import (
    _title_from_stepstone_url,
    make_stepstone_job_id,
    parse_job_details_response,
    parse_search_response,
    _DETAIL_BATCH_SIZE,
)

_UA             = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36")
_SALARY_TRIGGERS = ["Gehalt anzeigen", "Gehalt einblenden", "Salary"]
_PROBE_KEYWORDS  = ["Gehalt", "Stelle", "Bewerbung", "Erfahrung", "Aufgaben", "Profil"]


# ═══════════════════════════════════════════════════════════════
#  MCP mode
# ═══════════════════════════════════════════════════════════════

async def _mcp_refetch(targets: list[dict], config: dict, uid: str) -> dict[str, dict]:
    """
    Re-fetch details for target jobs via Stepstone MCP using fresh sessions
    per _DETAIL_BATCH_SIZE jobs.

    Returns {job_id: updated_fields} for each successfully fetched job.
    """
    try:
        from mcp.client.streamable_http import streamablehttp_client
        from mcp import ClientSession
    except ImportError:
        print("[ERROR] mcp package not installed: pip install mcp", file=sys.stderr)
        return {}

    stepstone_cfg = config.get("stepstone", {})
    server_url    = stepstone_cfg.get("server_url", "http://127.0.0.1:8000/mcp")
    radius        = stepstone_cfg.get("radius_km", 50)

    # Build keyword list per (group_id, zip_code) using config
    kw_map: dict[str, list[str]] = {}
    for grp in config["job_search"]["keyword_groups"]:
        gid  = grp["group_id"]
        seen: set[str] = set()
        kws:  list[str] = []
        for lang in ("en", "de"):
            for kw in grp["primary_keywords"].get(lang, []):
                if kw not in seen:
                    seen.add(kw)
                    kws.append(kw)
        kw_map[gid] = kws

    # Group targets by (group_id, zip_code) to minimise search_jobs calls
    from collections import defaultdict
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for job in targets:
        key = (job.get("_group_id", ""), job.get("_zip_code", ""))
        groups[key].append(job)

    fetched: dict[str, dict] = {}

    for (gid, zip_code), group_jobs in groups.items():
        keywords = kw_map.get(gid, [])
        if not keywords:
            print(f"  [WARN] no keywords for group {gid}, skipping {len(group_jobs)} jobs",
                  file=sys.stderr)
            continue

        search_args = {"search_terms": keywords, "zip_code": zip_code, "radius": radius}
        total = len(group_jobs)
        print(f"\n  Group {gid} @ {zip_code}: {total} jobs to refetch "
              f"({(total + _DETAIL_BATCH_SIZE - 1) // _DETAIL_BATCH_SIZE} batches)")

        for batch_start in range(0, total, _DETAIL_BATCH_SIZE):
            batch = group_jobs[batch_start:batch_start + _DETAIL_BATCH_SIZE]

            try:
                async with streamablehttp_client(server_url) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()

                        # Fresh session_id for this batch
                        try:
                            res = await asyncio.wait_for(
                                session.call_tool("search_jobs", search_args), timeout=30.0)
                        except asyncio.TimeoutError:
                            print(f"    [WARN] search_jobs timeout (batch {batch_start})",
                                  file=sys.stderr)
                            continue

                        fresh_text = res.content[0].text or "" if res.content else ""
                        fresh_id, job_count, _ = parse_search_response(fresh_text)
                        if not fresh_id:
                            print(f"    [WARN] no session_id (batch {batch_start})", file=sys.stderr)
                            continue
                        print(f"    Batch {batch_start // _DETAIL_BATCH_SIZE + 1}: "
                              f"session={fresh_id[:8]}... server_count={job_count}")

                        for job in batch:
                            jid       = job["job_id"]
                            job_url   = job.get("url", "")
                            slug_title = _title_from_stepstone_url(job_url)
                            query     = slug_title or job.get("title", "") or f"job_{jid}"

                            try:
                                detail = await asyncio.wait_for(
                                    session.call_tool("get_job_details", {
                                        "job_query":  query,
                                        "session_id": fresh_id,
                                    }),
                                    timeout=60.0,
                                )
                            except asyncio.TimeoutError:
                                print(f"      [WARN] timeout for {jid}", file=sys.stderr)
                                continue

                            detail_text = detail.content[0].text or "" if detail.content else ""
                            parsed = parse_job_details_response(detail_text)

                            # 3-tier title recovery
                            if not parsed["title"]:
                                parsed["title"] = slug_title or job.get("title", "")

                            if parsed["description_full"]:
                                fetched[jid] = parsed
                                print(f"      OK  {jid}: {parsed['title'][:50]} "
                                      f"desc={len(parsed['description_full'])} chars")
                            else:
                                print(f"      FAIL {jid}: empty description")

            except asyncio.TimeoutError:
                print(f"    [ERROR] batch {batch_start} timed out", file=sys.stderr)
            except Exception as e:
                print(f"    [ERROR] batch {batch_start}: {e}", file=sys.stderr)

            await asyncio.sleep(1.0)  # polite pause between batches

    return fetched


# ═══════════════════════════════════════════════════════════════
#  HTTP mode (probe + fetch)
# ═══════════════════════════════════════════════════════════════

class _StripTags(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True
        elif tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)


def _strip_html(raw: str) -> str:
    p = _StripTags()
    try:
        p.feed(raw)
    except Exception:
        pass
    return _html.unescape("".join(p._parts))


def _http_get(url: str, max_retries: int = 3) -> str | None:
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": _UA, "Accept-Language": "de-DE,de;q=0.9"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            print(f"    [HTTP {e.code}] attempt {attempt}/{max_retries}", file=sys.stderr)
            if e.code in (403, 429):
                time.sleep(5 * attempt)
        except Exception as e:
            print(f"    [ERROR] attempt {attempt}/{max_retries}: {e}", file=sys.stderr)
            time.sleep(2)
    return None


def _http_extract(plain: str) -> dict:
    result = {"title": "", "company": "", "location": "", "description_full": ""}
    trigger = next((t for t in _SALARY_TRIGGERS if t in plain), None)
    if trigger:
        after = plain.split(trigger, 1)[1].strip()
        after = re.sub(r"^\S[^\n]{0,120}\n", "", after).strip()
        result["description_full"] = after
    else:
        blocks = [b.strip() for b in re.split(r"\n{2,}", plain) if len(b.strip()) > 200]
        if blocks:
            result["description_full"] = max(blocks, key=len)
    lines = [l.strip() for l in plain.splitlines() if l.strip()]
    for i, line in enumerate(lines[:40]):
        if 3 <= len(line.split()) <= 10 and not re.search(r"https?://|^\d+$|^[A-Z]{2,}\s*$", line):
            result["title"]   = result["title"]   or line
            result["company"] = result["company"] or (lines[i+1] if i+1 < len(lines) else "")
            result["location"]= result["location"]or (lines[i+2] if i+2 < len(lines) else "")
            break
    return result


# ═══════════════════════════════════════════════════════════════
#  Shared: write-back + dedup
# ═══════════════════════════════════════════════════════════════

def _apply_and_save(jobs: list[dict], fetched: dict[str, dict], raw_path: Path) -> int:
    """Merge fetched results into jobs list, atomic-write, return success count."""
    job_index = {j["job_id"]: j for j in jobs}
    success = 0
    for jid, parsed in fetched.items():
        if jid not in job_index:
            continue
        j = job_index[jid]
        if parsed.get("title") and not j.get("title"):
            j["title"]    = parsed["title"]
        if parsed.get("company") and not j.get("company"):
            j["company"]  = parsed["company"]
        if parsed.get("location") and not j.get("location"):
            j["location"] = parsed["location"]
        j["description_full"]    = parsed["description_full"]
        j["description_snippet"] = parsed["description_full"][:800]
        j["_needs_refetch"]      = False
        success += 1

    tmp = raw_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(list(job_index.values()), ensure_ascii=False, indent=2),
                   encoding="utf-8")
    os.replace(tmp, raw_path)
    return success


def _run_dedup(batch_id: str, uid: str):
    print(f"\nRunning dedup --force for batch {batch_id} ...")
    r = subprocess.run(
        [sys.executable,
         str(Path(__file__).resolve().parent / "search_state.py"),
         "--mode", "dedup", "--batch-id", batch_id, "--uid", uid, "--force"],
        capture_output=False,
    )
    if r.returncode != 0:
        print("[WARN] dedup exited non-zero", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Refetch Stepstone job details")
    parser.add_argument("--batch-id",    required=True)
    parser.add_argument("--uid",         default="leon")
    parser.add_argument("--mode",        default="mcp", choices=["mcp", "http"])
    parser.add_argument("--delay",       type=float, default=1.5,
                        help="Seconds between HTTP requests (http mode only)")
    parser.add_argument("--max-retries", type=int,   default=3,
                        help="HTTP retry count (http mode only)")
    args = parser.parse_args()

    _ss.init_paths(args.uid)

    raw_path = _ss.TEMP_DIR / f"raw_results_{args.batch_id}.json"
    if not raw_path.exists():
        print(f"[ERROR] Not found: {raw_path}", file=sys.stderr)
        sys.exit(1)

    jobs: list[dict] = json.loads(raw_path.read_text(encoding="utf-8"))
    targets = [j for j in jobs if j.get("url") and not j.get("description_full")]
    print(f"Batch {args.batch_id}: {len(jobs)} total, {len(targets)} need refetch  [mode={args.mode}]")

    if not targets:
        print("Nothing to refetch.")
        return

    # ── MCP mode ──────────────────────────────────────────────
    if args.mode == "mcp":
        base = Path(__file__).resolve().parent.parent / "users" / args.uid
        cfg_path = base / "config.json"
        if not cfg_path.exists():
            print(f"[ERROR] config not found: {cfg_path}", file=sys.stderr)
            sys.exit(1)
        config = json.loads(cfg_path.read_text(encoding="utf-8"))

        fetched = asyncio.run(_mcp_refetch(targets, config, args.uid))
        success = _apply_and_save(jobs, fetched, raw_path)
        failed  = len(targets) - success
        print(f"\nSummary: {success} fetched / {failed} failed — updated {raw_path.name}")
        if success > 0:
            _run_dedup(args.batch_id, args.uid)
        return

    # ── HTTP mode ─────────────────────────────────────────────
    probe_url = targets[0]["url"]
    print(f"Probe: {probe_url[:80]} ...")
    probe_html = _http_get(probe_url, args.max_retries)
    if not probe_html:
        print("[ERROR] Probe failed — connection error.", file=sys.stderr)
        sys.exit(1)
    plain = _strip_html(probe_html)
    if not (len(plain) > 1000 and any(kw in plain for kw in _PROBE_KEYWORDS)):
        print("[ERROR] JS rendering detected — Stepstone blocks urllib on job pages.\n"
              "  Use --mode mcp instead.", file=sys.stderr)
        sys.exit(1)
    print("Probe OK — SSR content confirmed.\n")

    fetched: dict[str, dict] = {}
    for i, job in enumerate(targets, 1):
        jid = job["job_id"]
        url = job["url"]
        print(f"  [{i}/{len(targets)}] {url[-60:]}")
        html_text = _http_get(url, args.max_retries)
        if html_text:
            extracted = _http_extract(_strip_html(html_text))
            if len(extracted["description_full"]) > 100:
                fetched[jid] = extracted
                print(f"    OK  desc={len(extracted['description_full'])} chars")
            else:
                print(f"    FAIL (short desc)")
        else:
            print(f"    FAIL (fetch error)")
        time.sleep(args.delay)

    success = _apply_and_save(jobs, fetched, raw_path)
    failed  = len(targets) - success
    print(f"\nSummary: {success} fetched / {failed} failed — updated {raw_path.name}")
    if success > 0:
        _run_dedup(args.batch_id, args.uid)


if __name__ == "__main__":
    main()
