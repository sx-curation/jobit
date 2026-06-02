#!/usr/bin/env python3
"""
scripts/run_phase2_search.py

Phase 2B: 搜索所有 group 的 primary keywords，收集 job_ids，
并调用 get_job_details 获取详细信息，最终保存为 raw_results_<batch_id>.json。

特点：
- 只搜索 primary keywords（EN + DE），不搜索所有 job_family（数量太多）
- 每个关键词 max_pages=1（约 10 条结果）
- 通过 get_job_details 获取标题、公司、描述等结构化信息
- 自动去重 job_id（避免同一职位被多个关键词重复抓取）
- 关键词并行搜索（max_workers=3）
- 实时进度写入 output/temp/_search_progress.log
- detail 批次完成后立即增量写 _phase2_temp_partial.json，防崩溃丢数据
"""

import argparse
import itertools
import json
import os
import subprocess
import sys
import threading
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from common import UVX, make_mcp_proc, send_recv
from search_state import load_cv_skills, quick_score

# Fix Windows GBK crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

OUTPUT_DIR    = Path("output")
TEMP_DIR      = Path("output/temp")
CONFIG_PATH   = Path("config.json")
PROGRESS_LOG  = TEMP_DIR / "_search_progress.log"
PARTIAL_SAVE  = TEMP_DIR / "_phase2_temp_partial.json"

_progress_lock = threading.Lock()
_seen_lock     = threading.Lock()


# ─────────────────────────────────────────────
# MCP helpers
# ─────────────────────────────────────────────

def make_proc():
    return make_mcp_proc()


def initialize_proc(proc, timeout=15):
    """Perform MCP handshake. timeout reduced from 30→15s."""
    init = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "linkedin-cv-agent", "version": "1.0"},
        },
    }
    resp = send_recv(proc, init, timeout=timeout)
    if not resp or "result" not in resp:
        return False
    notif = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    proc.stdin.write(json.dumps(notif) + "\n")
    proc.stdin.flush()
    return True


def call_tool(proc, tool_name: str, args: dict, msg_id: int = 2, timeout=60) -> dict:
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


# ─────────────────────────────────────────────
# Noise filter + validity check
# ─────────────────────────────────────────────

_UI_NOISE = {"share", "save", "apply", "easy apply", "follow", "connect",
             "message", "dismiss", "report", "see more", "show more",
             "show more options", "show fewer options", "less", "more"}

_COMPANY_NOISE = re.compile(r'^\s*(share[sd]?|save[sd]?|apply|easy\s+apply)\s*$', re.I)


def _is_ui_noise(text: str) -> bool:
    return text.strip().lower() in _UI_NOISE


def parse_job_details_section(text: str) -> tuple[str, str, str]:
    lines = [l.strip() for l in text.split("\n") if l.strip() and not _is_ui_noise(l)]
    title    = lines[0].replace(" with verification", "").strip() if lines else ""
    company  = lines[1].strip() if len(lines) > 1 else ""
    location = lines[2].strip() if len(lines) > 2 else ""
    return title, company, location


def extract_job_ids_from_result(result: dict) -> list[str]:
    if not isinstance(result, dict):
        return []
    sc = result.get("structuredContent", {})
    if sc and "job_ids" in sc:
        return sc["job_ids"]
    if "job_ids" in result:
        return result["job_ids"]
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


_EXPIRED_MARKERS = [
    "no longer accepting applications",
    "nicht mehr aktiv",
    "bewerbungen werden nicht mehr",
]

def is_valid_job(job: dict) -> bool:
    company = job.get("company", "").strip()
    desc    = job.get("description_full", "").strip()
    if _COMPANY_NOISE.match(company):
        return False
    if len(desc) < 150:
        return False
    desc_lower = desc.lower()
    if any(marker in desc_lower for marker in _EXPIRED_MARKERS):
        return False
    return True


# ─────────────────────────────────────────────
# Progress logging
# ─────────────────────────────────────────────

def _log_progress(kw: str, found: int, cumulative: int) -> None:
    """Append one line to progress log; also print to stdout."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] kw={kw!r:<50}  found={found:3d}  cumulative={cumulative:3d}\n"
    with _progress_lock:
        print(line, end="", flush=True)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
            f.write(line)


# ─────────────────────────────────────────────
# 搜索单个关键词（供并行调用）
# ─────────────────────────────────────────────

_COOKIES_PATH   = Path.home() / ".linkedin-mcp" / "profile" / "Default" / "Network" / "Cookies"
_PORTABLE_COOKIES = Path.home() / ".linkedin-mcp" / "cookies.json"
_SOURCE_STATE     = Path.home() / ".linkedin-mcp" / "source-state.json"
_NO_SESSION_MSG   = "No valid LinkedIn session was found"
_LOGIN_WAIT_S     = 300  # max seconds to wait for user to log in


def _portable_auth_ready() -> bool:
    """True once the MCP login task has written the portable auth files."""
    return _PORTABLE_COOKIES.exists() and _SOURCE_STATE.exists()


def _wait_for_login() -> bool:
    """
    Block until the MCP login task writes portable auth files (cookies.json +
    source-state.json). These are written AFTER the user logs in the browser,
    within the SAME MCP process — do NOT kill the process while waiting.
    Returns True on success, False on timeout.
    """
    print(
        "\n[LOGIN] 浏览器窗口已打开，请登录 LinkedIn。\n"
        "        登录完成后脚本将自动继续（最多等待 5 分钟）…",
        flush=True,
    )
    deadline = time.monotonic() + _LOGIN_WAIT_S
    while time.monotonic() < deadline:
        if _portable_auth_ready():
            print("[LOGIN] 便携式 session 已写入，继续搜索…", flush=True)
            time.sleep(1)
            return True
        # Fallback: Chromium Cookies updated (older MCP versions)
        if _COOKIES_PATH.exists():
            time.sleep(5)  # give MCP time to export portable cookies
            if _portable_auth_ready():
                print("[LOGIN] Session 已保存，继续搜索…", flush=True)
                return True
        time.sleep(3)
    print("[LOGIN] 等待超时（5 分钟），跳过登录", file=sys.stderr)
    return False


def search_keyword(keywords: str, location: str, date_posted="past_month",
                   max_pages=1, timeout=60) -> list[str]:
    """
    返回 job_ids 列表。
    若 MCP 报 'No valid LinkedIn session'，保持同一进程存活等 login task 写入
    portable auth files，再在同一进程内重试（不杀进程，不新建进程）。
    """
    proc = make_proc()
    try:
        if not initialize_proc(proc, timeout=15):
            print(f"  [ERROR] initialize failed for '{keywords}'", file=sys.stderr)
            return []

        result = call_tool(proc, "search_jobs", {
            "keywords": keywords,
            "location": location,
            "date_posted": date_posted,
            "max_pages": max_pages,
        }, timeout=timeout)

        # Login required: keep the SAME proc alive while waiting —
        # the MCP's async login task runs inside this proc and writes
        # portable auth files only after user completes login in the browser.
        # Detect login-needed: explicit message OR any raw_text error with no portable auth
        raw_text = result.get("raw_text", "")
        login_needed = (
            _NO_SESSION_MSG in raw_text
            or (raw_text and not _portable_auth_ready())
        )
        if login_needed:
            if _wait_for_login():
                # Retry on the SAME proc — auth state is now READY inside it
                result = call_tool(proc, "search_jobs", {
                    "keywords": keywords,
                    "location": location,
                    "date_posted": date_posted,
                    "max_pages": max_pages,
                }, timeout=timeout)
            else:
                return []

        if "error" in result:
            print(f"  [ERROR] search '{keywords}': {result['error']}", file=sys.stderr)
            return []
        if "raw_text" in result:
            print(f"  [ERROR] search '{keywords}': {result['raw_text'][:200]}", file=sys.stderr)
            return []

        job_ids = extract_job_ids_from_result(result)
        print(f"  '{keywords}' -> {len(job_ids)} job_ids")
        return job_ids
    finally:
        kill_proc(proc)


def _search_one(kw: str, gid: str, glabel: str, location: str, date_posted: str,
                ktype: str = "primary"):
    """Worker函数：搜索单个关键词，返回 job entries list。"""
    job_ids = search_keyword(kw, location, date_posted, max_pages=1, timeout=60)
    time.sleep(1)  # per-thread rate limiting
    entries = [
        {"job_id": jid, "_keyword": kw, "_group_id": gid,
         "_group_label": glabel, "_source": "linkedin", "_keyword_type": ktype}
        for jid in job_ids
    ]
    return kw, entries


# ─────────────────────────────────────────────
# 获取职缺详情
# ─────────────────────────────────────────────

_JP_NOISE = {
    "share", "save", "apply", "easy apply", "follow", "connect",
    "message", "dismiss", "report", "see more", "show more",
    "show fewer options", "less", "more", "show more options",
    "show all", "get started", "about the job",
}


def _is_jp_noise(line: str) -> bool:
    s = line.strip().lower()
    if not s:
        return True
    if s in _JP_NOISE:
        return True
    if s.startswith("save ") or s.startswith("matches your job") or s.startswith("your ai"):
        return True
    return False


def _parse_job_posting(blob: str, jid: str) -> dict:
    """Parse MCP v3.2.4+ 'job_posting' single-blob format."""
    lines = blob.split("\n")

    non_noise = [(i, lines[i].strip()) for i in range(len(lines)) if not _is_jp_noise(lines[i])]

    company = non_noise[0][1] if len(non_noise) > 0 else ""
    title = ""
    location = ""
    if len(non_noise) > 1:
        title = non_noise[1][1].replace("\xa0", "").replace(" with verification", "").strip()
    if len(non_noise) > 2:
        location = non_noise[2][1].split("·")[0].strip()

    # Description: text between "About the job" and "See more"
    desc_start = -1
    desc_end = len(lines)
    for i, line in enumerate(lines):
        s = line.strip().lower()
        if s == "about the job":
            desc_start = i + 1
        elif desc_start > 0 and s in ("see more", "set alert for similar jobs"):
            desc_end = i
            break

    description = ""
    if desc_start > 0:
        description = "\n".join(l.strip() for l in lines[desc_start:desc_end]).strip()

    return {
        "job_id":              jid,
        "title":               title,
        "company":             company,
        "location":            location,
        "posted_at":           None,
        "description_snippet": description[:800],
        "description_full":    description,
        "url":                 f"https://www.linkedin.com/jobs/view/{jid}/",
    }


def _parse_sections(result: dict, jid: str) -> dict:
    sections = result.get("sections", {})

    # MCP v3.2.4+: single job_posting blob (no separate job_details/description)
    if "job_posting" in sections and "job_details" not in sections:
        return _parse_job_posting(sections["job_posting"], jid)

    # Legacy format
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
    """获取一批 job_ids 的详情，复用单个 MCP 进程。"""
    results = []
    proc = make_proc()
    try:
        if not initialize_proc(proc, timeout=15):
            print("  [ERROR] initialize failed for get_job_details", file=sys.stderr)
            return []

        msg_counter = itertools.count(10)
        for idx, jid in enumerate(job_ids, start=1):
            msg_id = next(msg_counter)
            result = call_tool(proc, "get_job_details", {"job_id": jid},
                               msg_id=msg_id, timeout=timeout)

            if "error" in result:
                print(f"  [WARN] get_job_details {jid}: {result['error']}", file=sys.stderr)
                results.append({
                    "job_id": jid, "title": "", "company": "", "location": "",
                    "description_snippet": "", "description_full": "",
                    "url": f"https://www.linkedin.com/jobs/view/{jid}/",
                    "posted_at": None, "_needs_refetch": True,
                    "_error_reason": str(result["error"]),
                })
                continue

            job = _parse_sections(result, jid)

            if not is_valid_job(job):
                time.sleep(3)
                retry = call_tool(proc, "get_job_details", {"job_id": jid},
                                  msg_id=next(msg_counter), timeout=timeout)
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
            print(f"    [{idx}/{len(job_ids)}] {jid}: "
                  f"{job.get('title','?')[:55]} @ {job.get('company','?')[:25]}")

    finally:
        kill_proc(proc)

    return results


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", help="只搜索指定 group_id（如 group-da）")
    parser.add_argument("--date-posted",
                        choices=["past_24_hours", "past_week", "past_month"],
                        help="覆盖 config.json 的 date_range_days 推算结果")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    job_search = config["job_search"]
    location = job_search["location"]
    date_range_days = job_search.get("date_range_days", 14)

    if args.date_posted:
        date_posted = args.date_posted
    elif date_range_days <= 1:
        date_posted = "past_24_hours"
    elif date_range_days <= 7:
        date_posted = "past_week"
    else:
        date_posted = "past_month"

    print(f"Phase 2B: 搜索职缺 | location={location} | date_posted={date_posted}")
    print("=" * 60)

    groups = job_search["keyword_groups"]
    if args.group:
        groups = [g for g in groups if g["group_id"] == args.group]
        if not groups:
            print(f"ERROR: group '{args.group}' not found in config.json", file=sys.stderr)
            sys.exit(1)

    # 清空进度日志（本次搜索开始）
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_LOG.write_text("", encoding="utf-8")

    print("实时进度写入:", PROGRESS_LOG)

    FALLBACK_THRESHOLD = 5
    SCORE_THRESHOLD    = 50

    all_jobs_with_details: list[dict] = []
    seen_job_ids: set[str] = set()
    total_fetched = 0  # running count for progress logging

    # max_workers=1: linkedin-scraper-mcp uses a shared profile directory (~/.linkedin-mcp/profile).
    # Concurrent MCP processes race on Cookies file → PermissionError → invalid-state-* accumulation.
    # Keep serial until MCP supports per-process isolation or we add a file lock.
    for group in groups:
        gid    = group["group_id"]
        glabel = group["group_label"]
        group_entries: list[dict] = []
        group_seen_ids: set[str] = set()
        cv_skills = load_cv_skills(f"output/cv_parsed_{gid}.json")

        # ── Phase A: primary keywords (EN + DE) ──────────────────────────────
        primary_kws = [kw for lang in ("en", "de")
                       for kw in group["primary_keywords"].get(lang, [])]
        print(f"\nGroup: {glabel} ({gid}) — {len(primary_kws)} primary keywords")
        print("=" * 60)

        with ThreadPoolExecutor(max_workers=1) as pool:
            futures = {
                pool.submit(_search_one, kw, gid, glabel, location, date_posted, "primary"): kw
                for kw in primary_kws
            }
            for future in as_completed(futures):
                kw = futures[future]
                try:
                    kw_out, entries = future.result()
                except Exception as exc:
                    print(f"  [ERROR] '{kw}': {exc}", file=sys.stderr)
                    _log_progress(kw, 0, total_fetched)
                    continue

                new_count = 0
                with _seen_lock:
                    for e in entries:
                        jid = e["job_id"]
                        if jid not in seen_job_ids:
                            seen_job_ids.add(jid)
                            group_seen_ids.add(jid)
                            group_entries.append(e)
                            new_count += 1
                        elif jid not in group_seen_ids:
                            group_seen_ids.add(jid)

                total_fetched += new_count
                _log_progress(kw_out, new_count, total_fetched)

        # ── Fetch details for primary jobs ────────────────────────────────────
        primary_ids = [e["job_id"] for e in group_entries]
        if primary_ids:
            print(f"\nFetching details for {gid} primary ({len(primary_ids)} jobs)…")
            print("=" * 60)
            primary_details = get_job_details_batch(primary_ids, timeout=120)
            detail_map = {d["job_id"]: d for d in primary_details}
        else:
            detail_map = {}

        primary_jobs: list[dict] = []
        for entry in group_entries:
            jid    = entry["job_id"]
            detail = detail_map.get(jid, {
                "job_id": jid, "title": "", "company": "", "location": "",
                "description_snippet": "", "description_full": "",
                "url": f"https://www.linkedin.com/jobs/view/{jid}/",
                "posted_at": None, "_needs_refetch": True,
            })
            primary_jobs.append({**detail, **{k: v for k, v in entry.items() if k.startswith("_")}})

        # ── Threshold check ───────────────────────────────────────────────────
        high_score_count = sum(1 for j in primary_jobs if quick_score(j, cv_skills) > SCORE_THRESHOLD)
        print(f"  {gid}: {high_score_count} jobs with score > {SCORE_THRESHOLD}")
        all_jobs_with_details.extend(primary_jobs)
        PARTIAL_SAVE.write_text(
            json.dumps(all_jobs_with_details, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  [incremental save] {len(all_jobs_with_details)} jobs → {PARTIAL_SAVE}")

        # ── Phase B: fallback to job_family.en if below threshold ────────────
        if high_score_count < FALLBACK_THRESHOLD:
            fallback_kws = list(dict.fromkeys(group.get("job_family", {}).get("en", [])))
            print(f"  [FALLBACK] {gid}: {high_score_count} < {FALLBACK_THRESHOLD} → "
                  f"searching {len(fallback_kws)} job_family.en keywords")

            fallback_entries: list[dict] = []

            with ThreadPoolExecutor(max_workers=1) as pool:
                futures = {
                    pool.submit(_search_one, kw, gid, glabel, location, date_posted, "fallback"): kw
                    for kw in fallback_kws
                }
                for future in as_completed(futures):
                    kw = futures[future]
                    try:
                        kw_out, entries = future.result()
                    except Exception as exc:
                        print(f"  [ERROR fallback] '{kw}': {exc}", file=sys.stderr)
                        _log_progress(kw, 0, total_fetched)
                        continue

                    new_count = 0
                    with _seen_lock:
                        for e in entries:
                            if e["job_id"] not in seen_job_ids:
                                seen_job_ids.add(e["job_id"])
                                fallback_entries.append(e)
                                new_count += 1

                    total_fetched += new_count
                    _log_progress(kw_out, new_count, total_fetched)

            if fallback_entries:
                fb_ids = [e["job_id"] for e in fallback_entries]
                print(f"\nFetching details for {gid} fallback ({len(fb_ids)} jobs)…")
                print("=" * 60)
                fb_details = get_job_details_batch(fb_ids, timeout=120)
                detail_map = {d["job_id"]: d for d in fb_details}
                for entry in fallback_entries:
                    jid    = entry["job_id"]
                    detail = detail_map.get(jid, {
                        "job_id": jid, "title": "", "company": "", "location": "",
                        "description_snippet": "", "description_full": "",
                        "url": f"https://www.linkedin.com/jobs/view/{jid}/",
                        "posted_at": None, "_needs_refetch": True,
                    })
                    all_jobs_with_details.append(
                        {**detail, **{k: v for k, v in entry.items() if k.startswith("_")}})
                PARTIAL_SAVE.write_text(
                    json.dumps(all_jobs_with_details, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(f"  [incremental save] {len(all_jobs_with_details)} jobs → {PARTIAL_SAVE}")

    # Final save (canonical output for save-raw step) — atomic write防崩溃截断
    temp_path = TEMP_DIR / "_phase2_temp.json"
    tmp = temp_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(all_jobs_with_details, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, temp_path)

    print(f"\nSaved {len(all_jobs_with_details)} jobs to {temp_path}")
    print(json.dumps({"fetched_total": len(all_jobs_with_details), "temp_file": str(temp_path)}))


if __name__ == "__main__":
    main()
