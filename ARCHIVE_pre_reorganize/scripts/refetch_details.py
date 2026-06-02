#!/usr/bin/env python3
"""
scripts/refetch_details.py

Re-fetches job details for all jobs in a batch with improved parsing.
Updates output/raw_results_<batch_id>.json in place.

Usage:
  python3 scripts/refetch_details.py --batch-id 20260406_001
"""

import json
import sys
import time
import re
import argparse
from pathlib import Path

from common import make_mcp_proc, send_recv

# Fix Windows GBK crash: reconfigure stdout/stderr to UTF-8 immediately at import time
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
OUTPUT_DIR = Path("output")
TEMP_DIR   = Path("output/temp")


def make_proc():
    return make_mcp_proc()


def initialize(proc):
    resp = send_recv(proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "linkedin-cv-agent", "version": "1.0"}},
    }, timeout=30)
    if not resp:
        return False
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized",
                                  "params": {}}) + "\n")
    proc.stdin.flush()
    return True


# LinkedIn UI element strings that appear as false positives in scraped text
_UI_NOISE = {"share", "save", "apply", "easy apply", "follow", "connect", "message",
             "dismiss", "report", "see more", "show more", "less", "more",
             "show more options", "show fewer options"}


def _is_ui_noise(text: str) -> bool:
    return text.strip().lower() in _UI_NOISE


def parse_job_details(text: str) -> tuple[str, str, str]:
    """Parse a job_details section; returns (title, company, location)."""
    lines = [l.strip() for l in text.split("\n") if l.strip() and not _is_ui_noise(l)]
    title = lines[0].replace(" with verification", "").strip() if lines else ""
    company = lines[1].strip() if len(lines) > 1 else ""
    location = lines[2].strip() if len(lines) > 2 else ""
    return title, company, location


def parse_job_posting(text: str, job_id: str) -> dict:
    """Parse the job_posting section text into structured fields."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # job_posting layout: company at line[0], title at line[3]
    # but line[0] can be a UI element like "Share" — skip those
    company = ""
    for line in lines[:3]:
        if not _is_ui_noise(line):
            company = line
            break

    title = ""
    for line in lines[2:6]:
        if line and not _is_ui_noise(line) and line != company:
            title = line.replace(" with verification", "").strip()
            break

    location = ""
    posted_at = ""
    description = ""

    # Location + date in lines 3–8
    for line in lines[3:9]:
        if any(kw in line for kw in ["Germany", "Remote", "Hybrid", "On-site", "Österreich", "Schweiz"]):
            parts = re.split(r"\s*[\xb7\u00b7]\s*", line)
            location = parts[0].strip() if parts else ""
            for p in parts[1:]:
                m = re.search(
                    r"((?:Reposted\s+)?\d+\s+(?:day|days|week|weeks|month|months|hour|hours)s?\s+ago)",
                    p
                )
                if m:
                    posted_at = m.group(1)
            break

    # Extract 'About the job' / 'Über die Stelle' content
    for marker in ["About the job", "Über die Stelle", "Job description", "Beschreibung"]:
        idx = text.find(marker)
        if idx >= 0:
            description = text[idx + len(marker):idx + len(marker) + 4000].strip()
            break

    return {
        "job_id":             job_id,
        "title":              title,
        "company":            company,
        "location":           location,
        "posted_at":          posted_at,
        "description_snippet": description[:800],
        "description_full":   description,
        "url":                f"https://www.linkedin.com/jobs/view/{job_id}/",
    }


def get_details_batch(job_ids: list[str], batch_num: int, timeout=120) -> dict[str, dict]:
    """Fetch details for a batch of job_ids. Returns {job_id: parsed_dict}."""
    results = {}
    proc = make_proc()
    try:
        if not initialize(proc):
            print(f"  [ERROR] initialize failed for batch {batch_num}", file=sys.stderr)
            return results

        for i, jid in enumerate(job_ids):
            msg_id = 10 + i
            req = {
                "jsonrpc": "2.0", "id": msg_id, "method": "tools/call",
                "params": {"name": "get_job_details", "arguments": {"job_id": jid}},
            }
            resp = send_recv(proc, req, timeout=timeout)
            if not resp or "result" not in resp:
                print(f"  [WARN] no response for job {jid}", file=sys.stderr)
                continue

            sc = resp["result"].get("structuredContent", {})
            sections = sc.get("sections", {})

            # Fallback: try to parse content text as JSON to get sections
            if not sections and "content" in resp["result"]:
                try:
                    data = json.loads(resp["result"]["content"][0]["text"])
                    sections = data.get("sections", {})
                except Exception:
                    pass

            # Prefer job_details section (title-first format, consistent with other scripts)
            # Fall back to job_posting section
            if "job_details" in sections:
                title, company, location = parse_job_details(sections["job_details"])
                parsed = {
                    "job_id":   jid,
                    "title":    title,
                    "company":  company,
                    "location": location,
                    "posted_at": "",
                    "description_snippet": "",
                    "description_full":    "",
                    "url": f"https://www.linkedin.com/jobs/view/{jid}/",
                }
                # Enrich with description
                if "description" in sections:
                    desc = sections["description"]
                    parsed["description_snippet"] = desc[:800]
                    parsed["description_full"] = desc
                # Try to extract posted_at from job_posting
                if "job_posting" in sections:
                    tmp = parse_job_posting(sections["job_posting"], jid)
                    if tmp.get("posted_at"):
                        parsed["posted_at"] = tmp["posted_at"]
                    if not parsed["location"] and tmp.get("location"):
                        parsed["location"] = tmp["location"]
            else:
                # No job_details section — fall back to job_posting parsing
                text = sections.get("job_posting", "")
                parsed = parse_job_posting(text, jid)
                if "description" in sections and not parsed.get("description_full"):
                    desc = sections["description"]
                    parsed["description_snippet"] = desc[:800]
                    parsed["description_full"] = desc

            results[jid] = parsed
            print(f"    [{i+1}/{len(job_ids)}] {jid}: {parsed['title'][:50]} @ {parsed['company'][:25]}")

    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--batch-size", type=int, default=12)
    args = parser.parse_args()

    # Check output/temp/ first, then fall back to output/ for legacy files
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    write_path = TEMP_DIR / f"raw_results_{args.batch_id}.json"
    data = None
    for base_dir in [TEMP_DIR, OUTPUT_DIR]:
        try:
            data = json.loads((base_dir / f"raw_results_{args.batch_id}.json").read_text(encoding="utf-8"))
            break
        except FileNotFoundError:
            continue
    if data is None:
        print(f"ERROR: raw_results_{args.batch_id}.json not found in output/temp/ or output/", file=sys.stderr)
        sys.exit(1)
    job_ids, metadata = [], {}
    for j in data:
        jid = j["job_id"]
        job_ids.append(jid)
        metadata[jid] = {k: v for k, v in j.items() if k.startswith("_") or k in ("job_id",)}

    print(f"Re-fetching details for {len(job_ids)} jobs in batch '{args.batch_id}'")
    print("=" * 60)

    all_details: dict[str, dict] = {}
    BS = args.batch_size

    for i in range(0, len(job_ids), BS):
        batch = job_ids[i:i+BS]
        bn = i // BS + 1
        total_batches = (len(job_ids) + BS - 1) // BS
        print(f"\nDetail batch {bn}/{total_batches} ({len(batch)} jobs)")
        details = get_details_batch(batch, bn, timeout=120)
        all_details.update(details)
        if i + BS < len(job_ids):
            time.sleep(3)  # Rate limiting

    # Merge: keep metadata (_keyword, _group_id, etc.) from original, update details
    updated = []
    for jid in job_ids:
        meta = metadata.get(jid, {"job_id": jid})
        detail = all_details.get(jid, {
            "job_id": jid, "title": "", "company": "", "location": "",
            "description_snippet": "", "description_full": "",
            "url": f"https://www.linkedin.com/jobs/view/{jid}/",
            "posted_at": None,
        })
        merged = {**detail, **{k: v for k, v in meta.items() if k not in ("job_id", "_needs_refetch")}}
        updated.append(merged)

    write_path.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\nUpdated {len(updated)} jobs in {write_path}")


if __name__ == "__main__":
    main()
