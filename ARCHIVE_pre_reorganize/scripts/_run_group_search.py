#!/usr/bin/env python3
"""
scripts/_run_group_search.py
搜索指定 group 的 primary keywords，抓取职位详情，保存原始结果。

用法：
  python scripts/_run_group_search.py --group group-da
  python scripts/_run_group_search.py --group group-da --batch-id 20260414_001
  python scripts/_run_group_search.py --group group-da --date-posted past_week
"""

import json
import re
import subprocess
import sys
import time
import argparse
from pathlib import Path

from common import UVX

# Fix Windows GBK crash: reconfigure stdout/stderr to UTF-8 immediately at import time
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
OUTPUT_DIR = Path("output")
TEMP_DIR   = Path("output/temp")
CONFIG_PATH = Path("config.json")

sys.path.insert(0, str(Path(__file__).parent))
from search_state import load_history, new_batch_id, save_raw_results


# ─── MCP subprocess helpers ───────────────────────────────────────────────────

def make_proc():
    return subprocess.Popen(
        [UVX, "linkedin-scraper-mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )


def send_recv(proc, msg: dict, timeout=120) -> dict | None:
    msg_id = msg.get("id")
    proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    deadline = time.time() + timeout
    while time.time() < deadline:
        raw = proc.stdout.readline()
        if not raw:
            time.sleep(0.1)
            continue
        try:
            resp = json.loads(raw.strip())
            if resp.get("id") == msg_id:
                return resp
        except json.JSONDecodeError:
            continue
    return None


def initialize_proc(proc) -> bool:
    resp = send_recv(proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "linkedin-cv-agent", "version": "1.0"},
        },
    }, timeout=30)
    if not resp or "result" not in resp:
        return False
    proc.stdin.write(json.dumps({"jsonrpc": "2.0",
                                  "method": "notifications/initialized",
                                  "params": {}}) + "\n")
    proc.stdin.flush()
    return True


def call_tool(proc, tool_name: str, args: dict, msg_id: int = 2, timeout=120) -> dict:
    req = {
        "jsonrpc": "2.0", "id": msg_id, "method": "tools/call",
        "params": {"name": tool_name, "arguments": args},
    }
    resp = send_recv(proc, req, timeout=timeout)
    if not resp:
        return {"error": f"{tool_name} timed out"}
    if "error" in resp:
        return {"error": resp["error"]}
    result = resp.get("result", {})
    if "structuredContent" in result:
        return result["structuredContent"]
    if "content" in result and result["content"]:
        try:
            return json.loads(result["content"][0]["text"])
        except Exception:
            return {"raw_text": result["content"][0].get("text", "")}
    return result


def kill_proc(proc):
    try:
        proc.stdin.close()
    except Exception:
        pass
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


# ─── Job ID extraction ────────────────────────────────────────────────────────

def extract_job_ids_from_result(result: dict) -> list[str]:
    """
    Extract job_ids from MCP search_jobs response.
    Tries structuredContent.job_ids first, then content[0].text JSON path.
    """
    if not isinstance(result, dict):
        return []
    # Primary path
    sc = result.get("structuredContent", {})
    if sc and "job_ids" in sc:
        return sc["job_ids"]
    # Also check top-level job_ids (returned by call_tool after unwrapping)
    if "job_ids" in result:
        return result["job_ids"]
    # Secondary: parse content text
    content = result.get("content", [])
    if content and isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    parsed = json.loads(item["text"])
                    if "job_ids" in parsed:
                        return parsed["job_ids"]
                except Exception:
                    pass
    return []


# ─── Noise filter + job detail parsing ───────────────────────────────────────

_UI_NOISE = {"share", "save", "apply", "easy apply", "follow", "connect",
             "message", "dismiss", "report", "see more", "show more",
             "show more options", "show fewer options", "less", "more"}

_COMPANY_NOISE = re.compile(r'^\s*(share[sd]?|save[sd]?|apply|easy\s+apply)\s*$', re.I)


def _is_ui_noise(text: str) -> bool:
    return text.strip().lower() in _UI_NOISE


def parse_job_details_section(text: str) -> tuple[str, str, str]:
    """Parse job_details section → (title, company, location). Filters UI noise."""
    lines = [l.strip() for l in text.split("\n") if l.strip() and not _is_ui_noise(l)]
    title    = lines[0].replace(" with verification", "").strip() if lines else ""
    company  = lines[1].strip() if len(lines) > 1 else ""
    location = lines[2].strip() if len(lines) > 2 else ""
    return title, company, location


def is_valid_job(job: dict) -> bool:
    """Return False if company looks like a UI artifact or description is too short."""
    company = job.get("company", "").strip()
    desc    = job.get("description_full", "").strip()
    if _COMPANY_NOISE.match(company):
        return False
    if len(desc) < 150:
        return False
    return True


# ─── Search ───────────────────────────────────────────────────────────────────

def search_keyword(keywords: str, location: str, date_posted="past_month",
                   max_pages=1, timeout=180) -> list[str]:
    """Returns list of job_ids."""
    proc = make_proc()
    try:
        if not initialize_proc(proc):
            print(f"  [ERROR] initialize failed for '{keywords}'", file=sys.stderr)
            return []
        result = call_tool(proc, "search_jobs", {
            "keywords":    keywords,
            "location":    location,
            "date_posted": date_posted,
            "max_pages":   max_pages,
        }, timeout=timeout)
        if "error" in result:
            print(f"  [ERROR] search '{keywords}': {result['error']}", file=sys.stderr)
            return []
        job_ids = extract_job_ids_from_result(result)
        print(f"  '{keywords}' -> {len(job_ids)} job_ids")
        return job_ids
    finally:
        kill_proc(proc)


# ─── Detail fetching with retry ───────────────────────────────────────────────

def _parse_sections(result: dict, jid: str) -> dict:
    """Parse MCP get_job_details result into a job dict."""
    sections = result.get("sections", {})
    job = {
        "job_id":              jid,
        "title":               "",
        "company":             "",
        "location":            "",
        "posted_at":           None,
        "description_snippet": "",
        "description_full":    "",
        "url":                 f"https://www.linkedin.com/jobs/view/{jid}/",
    }
    if "job_details" in sections:
        title, company, location = parse_job_details_section(sections["job_details"])
        job["title"]    = title
        job["company"]  = company
        job["location"] = location
    if "description" in sections:
        desc = sections["description"]
        job["description_snippet"] = desc[:800]
        job["description_full"]    = desc
    return job


def get_job_details_batch(job_ids: list[str], timeout=120) -> list[dict]:
    """Fetch details for a batch. Retries once per job if invalid result."""
    results = []
    proc = make_proc()
    try:
        if not initialize_proc(proc):
            print("  [ERROR] initialize failed for get_job_details", file=sys.stderr)
            return []

        for i, jid in enumerate(job_ids):
            msg_id = i + 10
            result = call_tool(proc, "get_job_details", {"job_id": jid},
                               msg_id=msg_id, timeout=timeout)

            if "error" in result:
                print(f"  [WARN] get_job_details {jid}: {result['error']}", file=sys.stderr)
                job = {
                    "job_id": jid, "title": "", "company": "", "location": "",
                    "description_snippet": "", "description_full": "",
                    "url": f"https://www.linkedin.com/jobs/view/{jid}/",
                    "posted_at": None, "_needs_refetch": True,
                }
                results.append(job)
                continue

            job = _parse_sections(result, jid)

            # Single retry if invalid (noisy company or empty description)
            if not is_valid_job(job):
                time.sleep(3)
                retry = call_tool(proc, "get_job_details", {"job_id": jid},
                                  msg_id=msg_id + 1000, timeout=timeout)
                if "error" not in retry:
                    job = _parse_sections(retry, jid)
                job["_needs_refetch"] = not is_valid_job(job)
                if job["_needs_refetch"]:
                    print(f"  [WARN] {jid}: invalid after retry "
                          f"(co='{job['company']}', desc_len={len(job.get('description_full',''))})",
                          file=sys.stderr)
            else:
                job["_needs_refetch"] = False

            results.append(job)
            print(f"    [{i+1}/{len(job_ids)}] {jid}: {job.get('title','?')[:55]} @ {job.get('company','?')[:25]}")

    finally:
        kill_proc(proc)

    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Search one group's jobs on LinkedIn")
    parser.add_argument("--group",       required=True, help="group_id (e.g. group-da)")
    parser.add_argument("--batch-id",    default=None,  help="batch id; auto-generated if omitted")
    parser.add_argument("--date-posted", default=None,
                        choices=["past_24_hours", "past_week", "past_month"],
                        help="override date filter (default: derived from config.date_range_days)")
    args = parser.parse_args()

    config    = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    job_search = config["job_search"]
    location   = job_search["location"]

    # Derive date_posted from config unless overridden
    date_range = job_search.get("date_range_days", 14)
    if args.date_posted:
        date_posted = args.date_posted
    elif date_range <= 1:
        date_posted = "past_24_hours"
    elif date_range <= 7:
        date_posted = "past_week"
    else:
        date_posted = "past_month"

    # Find target group
    target_group = next(
        (g for g in job_search["keyword_groups"] if g["group_id"] == args.group),
        None
    )
    if not target_group:
        print(f"[ERROR] Group '{args.group}' not found in config.json", file=sys.stderr)
        sys.exit(1)

    # Auto-generate batch_id if not provided
    if not args.batch_id:
        h = load_history()
        args.batch_id = new_batch_id(h)

    gid    = target_group["group_id"]
    glabel = target_group.get("group_label", gid)

    print(f"Phase 2B: 搜索职缺 | group={gid} | location={location} | date_posted={date_posted}")
    print(f"Batch ID: {args.batch_id}")
    print("=" * 60)

    # Collect keywords (primary only, EN + DE, deduped)
    seen_kws: set[str] = set()
    keywords_ordered: list[str] = []
    for lang in ("en", "de"):
        for kw in target_group["primary_keywords"].get(lang, []):
            if kw not in seen_kws:
                seen_kws.add(kw)
                keywords_ordered.append(kw)

    # Step 1: search_jobs per keyword → collect job_ids
    all_job_entries: list[dict] = []
    seen_job_ids: set[str] = set()

    for i, kw in enumerate(keywords_ordered, 1):
        print(f"[{i}/{len(keywords_ordered)}] Searching: {kw!r}", flush=True)
        try:
            job_ids = search_keyword(kw, location, date_posted, max_pages=1, timeout=180)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)
            continue
        time.sleep(2)
        for jid in job_ids:
            if jid not in seen_job_ids:
                seen_job_ids.add(jid)
                all_job_entries.append({
                    "job_id":       jid,
                    "_keyword":     kw,
                    "_group_id":    gid,
                    "_group_label": glabel,
                    "_source":      "linkedin",
                })

    print(f"\n[total_ids] {len(all_job_entries)} unique job_ids collected")

    if not all_job_entries:
        print("[WARN] No job_ids found — saving empty batch")
        out = save_raw_results(args.batch_id, [])
        print(f"[saved] batch_id={args.batch_id}  raw_file={out}  total=0")
        print(f"BATCH_ID={args.batch_id}")
        return

    # Step 2: fetch details in batches
    print(f"\nFetching job details for {len(all_job_entries)} jobs...")
    print("=" * 60)

    BATCH_SIZE = 15
    all_jobs_with_details: list[dict] = []

    for i in range(0, len(all_job_entries), BATCH_SIZE):
        batch       = all_job_entries[i:i + BATCH_SIZE]
        batch_ids   = [e["job_id"] for e in batch]
        bn          = i // BATCH_SIZE + 1
        total_batches = (len(all_job_entries) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\nDetail batch {bn}/{total_batches} ({len(batch_ids)} jobs)")

        details    = get_job_details_batch(batch_ids, timeout=120)
        detail_map = {d["job_id"]: d for d in details}

        for entry in batch:
            jid    = entry["job_id"]
            detail = detail_map.get(jid, {
                "job_id": jid, "title": "", "company": "", "location": "",
                "description_snippet": "", "description_full": "",
                "url": f"https://www.linkedin.com/jobs/view/{jid}/",
                "posted_at": None, "_needs_refetch": True,
            })
            merged = {**detail, **{k: v for k, v in entry.items() if k.startswith("_")}}
            all_jobs_with_details.append(merged)

        if i + BATCH_SIZE < len(all_job_entries):
            time.sleep(3)

    # Step 3: save via search_state (updates search_history.json)
    out = save_raw_results(args.batch_id, all_jobs_with_details)
    print(f"\n[saved] batch_id={args.batch_id}  raw_file={out}  total={len(all_jobs_with_details)}")
    print(json.dumps({
        "batch_id":      args.batch_id,
        "group_id":      gid,
        "fetched_total": len(all_jobs_with_details),
        "raw_file":      str(out),
    }, ensure_ascii=False))
    print(f"BATCH_ID={args.batch_id}")


if __name__ == "__main__":
    main()
