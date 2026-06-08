#!/usr/bin/env python3
"""
scripts/search_state.py

管理搜索状态：offset 计算、去重、match score 预排序。

中间文件路径：
  output/temp/raw_results_<batch_id>.json   ← 搜索原始结果（步骤 B 写入）
  output/search_history.json                ← 批次历史 + 去重状态

search_history.json 的 batch 结构：
  {
    "batch_id": "20240405_001",
    "date": "2024-04-05",
    "raw_results_file": "output/temp/raw_results_20240405_001.json",
    "dedup_done": false,      ← 步骤 B 写入时为 false，步骤 C 完成后改为 true
    "fetched_total": 200,
    "new_total": 47,
    ...
  }

用法：
  # 查询本次各关键词的起始 offset
  python3 scripts/search_state.py --mode offset --config config.json

  # 保存搜索原始结果（步骤 B 完成后调用）
  python3 scripts/search_state.py --mode save-raw \
      --batch-id 20240405_001 \
      --input /path/to/fetched_results.json

  # 去重 + 预评分 + 排序（步骤 C，读取 output/raw_results_<batch_id>.json）
  python3 scripts/search_state.py --mode dedup \
      --batch-id 20240405_001 \
      --config config.json

  # 查看历史摘要
  python3 scripts/search_state.py --mode summary
"""

import json
import argparse
import os
import sys
import threading
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
import re

HISTORY_PATH:    Path = None  # type: ignore  # set by init_paths()
OUTPUT_DIR:      Path = None  # type: ignore
TEMP_DIR:        Path = None  # type: ignore
BATCH_STATE_TSV: Path = None  # type: ignore
LOCK_FILE:       Path = None  # type: ignore
_tsv_lock       = threading.Lock()


def init_paths(uid: str):
    global HISTORY_PATH, OUTPUT_DIR, TEMP_DIR, BATCH_STATE_TSV, LOCK_FILE
    base            = Path(__file__).resolve().parent.parent / "users" / uid
    OUTPUT_DIR      = base / "output"
    TEMP_DIR        = OUTPUT_DIR / "temp"
    HISTORY_PATH    = OUTPUT_DIR / "search_history.json"
    BATCH_STATE_TSV = TEMP_DIR / "batch_state.tsv"
    LOCK_FILE       = TEMP_DIR / ".search.lock"


# ─────────────────────────────────────────────
# 历史文件读写
# ─────────────────────────────────────────────

def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {"batches": [], "seen_jobs": {}}
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def save_history(h: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Atomic write: write to .tmp then rename to avoid corruption on crash
    tmp = HISTORY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, HISTORY_PATH)


# ─────────────────────────────────────────────
# batch_id 生成与查找
# ─────────────────────────────────────────────

def new_batch_id(h: dict) -> str:
    """生成今天的下一个 batch_id，格式：YYYYMMDD_NNN。"""
    today = date.today().isoformat()
    n = sum(1 for b in h["batches"] if b["date"] == today) + 1
    return f"{today.replace('-', '')}_{n:03d}"


def get_batch(h: dict, batch_id: str) -> dict | None:
    for b in h["batches"]:
        if b["batch_id"] == batch_id:
            return b
    return None


def raw_results_path(batch_id: str) -> Path:
    """返回该批次原始结果文件的路径（优先 output/temp/，向后兼容 output/）。"""
    temp_path = TEMP_DIR / f"raw_results_{batch_id}.json"
    if temp_path.exists():
        return temp_path
    legacy = OUTPUT_DIR / f"raw_results_{batch_id}.json"
    if legacy.exists():
        return legacy
    return temp_path  # 新文件默认写入 temp/


# ─────────────────────────────────────────────
# 批处理容错：TSV 状态、锁文件、失败追踪
# ─────────────────────────────────────────────

def append_batch_state(batch_id: str, job_id: str, source: str,
                       status: str, score: int = -1,
                       error: str = "-") -> None:
    """追加一行到 batch_state.tsv（append-only，线程安全）。
    status 枚举：done / failed / skipped_dup / skipped_score / pending
    """
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    with _tsv_lock:
        if not BATCH_STATE_TSV.exists():
            BATCH_STATE_TSV.write_text(
                "batch_id\tjob_id\tsource\tstatus\tscore\terror\tcompleted_at\n",
                encoding="utf-8"
            )
        ts = datetime.now().isoformat(timespec="seconds")
        line = f"{batch_id}\t{job_id}\t{source}\t{status}\t{score}\t{error}\t{ts}\n"
        with open(BATCH_STATE_TSV, "a", encoding="utf-8") as f:
            f.write(line)


def acquire_lock() -> bool:
    """尝试获取搜索进程锁。返回 True=成功，False=另一进程在运行。"""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            import psutil
            if psutil.pid_exists(pid):
                return False
        except Exception:
            pass  # psutil 未安装或读取失败 → 跳过存活检测，直接覆盖锁
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock() -> None:
    """释放搜索进程锁。"""
    LOCK_FILE.unlink(missing_ok=True)


def mark_job_failed(batch_id: str, job_id: str) -> None:
    """将 job_id 标记为失败，写入对应 batch 的 failed_jobs 列表。"""
    h = load_history()
    b = get_batch(h, batch_id)
    if b is None:
        return
    b.setdefault("failed_jobs", [])
    if job_id not in b["failed_jobs"]:
        b["failed_jobs"].append(job_id)
    b.setdefault("retry_count", 0)
    save_history(h)


def get_failed_jobs(batch_id: str) -> list[str]:
    """返回指定 batch 的失败 job_id 列表（旧批次无此字段时返回 []）。"""
    h = load_history()
    b = get_batch(h, batch_id)
    return b.get("failed_jobs", []) if b else []


# ─────────────────────────────────────────────
# config 辅助
# ─────────────────────────────────────────────

def build_group_meta(config: dict) -> dict[str, dict]:
    """返回 {group_id: {cv_file, cv_parsed, group_label}}。"""
    meta = {}
    for g in config["job_search"].get("keyword_groups", []):
        gid = g["group_id"]
        meta[gid] = {
            "cv_file":     g.get("cv_file", ""),
            "cv_parsed":   f"output/cv_parsed_{gid}.json",
            "group_label": g.get("group_label", gid),
        }
    return meta


def flatten_keywords(config: dict) -> list[str]:
    """展平所有 group 的 primary + job_family 关键词（EN + DE），保序去重。"""
    seen: dict[str, bool] = {}
    for group in config["job_search"].get("keyword_groups", []):
        for lang in ("en", "de"):
            for kw in group["primary_keywords"].get(lang, []):
                seen[kw] = True
            for kw in group["job_family"].get(lang, []):
                seen[kw] = True
    return list(seen.keys())


# ─────────────────────────────────────────────
# offset 计算
# ─────────────────────────────────────────────

def compute_offsets(config: dict) -> dict[str, int]:
    """
    返回 {keyword: offset}。

    同天多批次：offset = 该词在当天所有已有批次中累计 fetched 数。
    跨天：offset 归零（seen_jobs 去重仍生效）。
    """
    h = load_history()
    today = date.today().isoformat()
    keywords = flatten_keywords(config)
    offsets = {kw: 0 for kw in keywords}

    for batch in h["batches"]:
        if batch["date"] != today:
            continue
        for kw, count in batch.get("fetched_per_keyword", {}).items():
            if kw in offsets:
                offsets[kw] += count

    return offsets


# ─────────────────────────────────────────────
# 保存原始搜索结果（步骤 B）
# ─────────────────────────────────────────────

def save_raw_results(batch_id: str, raw_results: list[dict]) -> Path:
    """
    将步骤 B 的原始搜索结果写入 output/raw_results_<batch_id>.json，
    并在 search_history.json 中创建 batch 条目（dedup_done=false）。

    返回写入的文件路径。
    """
    h = load_history()
    today = date.today().isoformat()

    # 确认 batch_id 不重复
    if get_batch(h, batch_id):
        # 已存在则更新（允许重试）
        existing = get_batch(h, batch_id)
        existing["fetched_total"] = len(raw_results)
        existing["raw_results_file"] = str(raw_results_path(batch_id))
    else:
        # 统计每个关键词的 fetched 数
        fetched_per_keyword: dict[str, int] = {}
        fetched_per_source:  dict[str, int] = {}
        for job in raw_results:
            kw  = job.get("_keyword", "unknown")
            src = job.get("_source",  "linkedin")
            fetched_per_keyword[kw]  = fetched_per_keyword.get(kw, 0) + 1
            fetched_per_source[src]  = fetched_per_source.get(src, 0) + 1

        # 自动检测触发了 job_family fallback 的 group（从 _keyword_type 字段）
        groups_with_fallback: list[str] = list({
            j["_group_id"] for j in raw_results
            if j.get("_keyword_type") == "fallback" and j.get("_group_id")
        })
        fallback_fetched: dict[str, int] = {}
        for j in raw_results:
            if j.get("_keyword_type") == "fallback":
                gid = j.get("_group_id", "")
                if gid:
                    fallback_fetched[gid] = fallback_fetched.get(gid, 0) + 1

        out_path_str = str(TEMP_DIR / f"raw_results_{batch_id}.json")
        h["batches"].append({
            "batch_id":             batch_id,
            "date":                 today,
            "raw_results_file":     out_path_str,
            "dedup_done":           False,    # 步骤 C 完成后改为 True
            "fetched_total":        len(raw_results),
            "fetched_per_keyword":  fetched_per_keyword,
            "fetched_per_source":   fetched_per_source,
            "groups_with_fallback": groups_with_fallback,   # groups that triggered job_family fallback
            "fallback_fetched":     fallback_fetched,       # {group_id: fallback_job_count}
            # 以下字段由步骤 C（dedup）填充
            "new_total":            None,
            "displayed":            None,
            "skipped_duplicate":    None,
            "hidden_low_score":     None,
            "job_ids":              [],
        })

    # 写入原始结果文件（统一写入 output/temp/），原子写防崩溃截断
    out_path = TEMP_DIR / f"raw_results_{batch_id}.json"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(raw_results, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, out_path)

    save_history(h)

    return out_path


# ─────────────────────────────────────────────
# 快速预评分
# ─────────────────────────────────────────────

def load_cv_skills(cv_parsed_path: str) -> list[str]:
    p = Path(cv_parsed_path)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("skills", [])
    except Exception:
        return []


@lru_cache(maxsize=None)
def _expand_skill_tokens(skill: str) -> list[str]:
    """
    Split a multi-word skill phrase into lowercased sub-terms for matching.
    Splits on & , / ( ) and whitespace runs.
    Minimum token length: 2 chars (preserves QA, ML, KPI, SQL, SEO).
    Always includes the lowercased full phrase as first element.
    """
    sl = skill.lower()
    parts = re.split(r"[&,/()\s]+", sl)
    tokens = [t.strip() for t in parts if len(t.strip()) >= 2]
    result = [sl]
    for t in tokens:
        if t != sl:
            result.append(t)
    return result


def quick_score(job: dict, cv_skills: list[str]) -> int:
    """
    关键词重叠预评分（0–100），用于 Phase 2 展示排序。
    title 命中 +5/技能，text 命中 +2/技能，上限 100。
    无 CV 数据时返回 50。

    匹配策略：
    - 每个 skill 拆分为子词（按 & , / ( )），任一子词命中即得分
    - description_snippet < 100 chars 时 fallback 到 description_full
    """
    if not cv_skills:
        return 50

    title = (job.get("title") or "").lower()

    snippet = (job.get("description_snippet") or "")
    full    = (job.get("description_full")    or "")
    text    = (snippet if len(snippet) >= 100 else full).lower()

    score = 0
    for skill in cv_skills:
        tokens = _expand_skill_tokens(skill)
        if any(t in title for t in tokens):
            score += 5
        elif any(t in text for t in tokens):
            score += 2

    return min(score, 100)


# ─────────────────────────────────────────────
# 去重 + 排序（步骤 C）
# ─────────────────────────────────────────────

def dedup_and_sort(batch_id: str, config: dict) -> dict:
    """
    从 output/temp/raw_results_<batch_id>.json 读取原始结果（向后兼容 output/），执行：
      1. job_id 去重
      2. 各 group 独立预评分
      3. 降序排序
      4. 截取前 max_display 条
      5. 更新 search_history.json（填充去重统计，dedup_done=True）

    返回结构化结果（含 display_jobs，每条附 cv_file / cv_parsed）。
    """
    h = load_history()
    seen = h["seen_jobs"]
    group_meta  = build_group_meta(config)
    max_display = config["job_search"].get("max_display", 30)

    # 读取原始结果
    rp = raw_results_path(batch_id)
    if not rp.exists():
        print(f"ERROR: 原始结果文件不存在：{rp}", file=sys.stderr)
        sys.exit(1)

    raw_results: list[dict] = json.loads(rp.read_text(encoding="utf-8"))

    # 预加载各 group 的 CV 技能
    cv_skills_cache: dict[str, list[str]] = {
        gid: load_cv_skills(meta["cv_parsed"])
        for gid, meta in group_meta.items()
    }

    # ── Step 1：去重
    # 规则 A：job_id + 公司 + 职位三者完全相同 → 过滤（LinkedIn 稳定 URL）
    # 规则 B：公司 + 职位完全相同 → 过滤（Stepstone session URL 每次变化导致 job_id 不同）
    new_jobs: list[dict] = []
    skipped = 0

    # 构建 (company, title) → jid 反向索引，用于规则 B 及 last_seen 更新
    seen_ct: dict[tuple[str, str], str] = {
        (v["company"].lower().strip(), v["title"].lower().strip()): jid
        for jid, v in seen.items()
        if v.get("company") and v.get("title")
    }

    today = date.today().isoformat()

    for job in raw_results:
        jid = str(job.get("job_id") or job.get("id") or "")
        if not jid:
            continue
        co    = (job.get("company") or "").lower().strip()
        title = (job.get("title")   or "").lower().strip()

        # 规则 A：job_id 已见过且公司+职位一致
        if jid in seen:
            ex = seen[jid]
            if ex["company"].lower() == co and ex["title"].lower() == title:
                seen[jid]["last_seen"] = today
                skipped += 1
                continue

        # 规则 B：(公司, 职位) 已见过（跨批次跨 URL 去重，主要针对 Stepstone）
        if co and title and (co, title) in seen_ct:
            orig_jid = seen_ct[(co, title)]
            if orig_jid in seen:
                seen[orig_jid]["last_seen"] = today
            skipped += 1
            continue

        seen_ct[(co, title)] = jid  # 批次内去重
        new_jobs.append(job)

    # ── Step 2：预评分 + 标记低分（per-group，不跨组混用）
    min_score = config.get("job_search", {}).get("min_score_for_analysis", 20)
    for job in new_jobs:
        gid    = job.get("_group_id", "")
        skills = cv_skills_cache.get(gid, [])
        job["match_score_preview"] = quick_score(job, skills)
        job["skip_analysis"] = job["match_score_preview"] < min_score
        meta = group_meta.get(gid, {})
        job["cv_file"]   = meta.get("cv_file",   "")
        job["cv_parsed"] = meta.get("cv_parsed", "")

    # ── Step 3：降序排序
    new_jobs.sort(key=lambda j: j["match_score_preview"], reverse=True)

    # ── Step 4：截取
    display_jobs = new_jobs[:max_display]
    hidden_count = max(0, len(new_jobs) - max_display)

    # ── Step 5：更新 seen_jobs（所有 new_jobs，不限于 display_jobs）
    # Bug fix: 原代码只把 display_jobs 加入 seen_jobs，导致隐藏低分 job 在下次搜索时被视为"新职缺"
    for job in new_jobs:
        jid = str(job.get("job_id") or job.get("id") or "")
        if not jid:
            continue
        seen[jid] = {
            "company":             job.get("company", ""),
            "title":               job.get("title",   ""),
            "first_seen":          today,
            "last_seen":           today,
            "batch_id":            batch_id,
            "group_id":            job.get("_group_id",  ""),
            "cv_file":             job.get("cv_file",    ""),
            "keyword":             job.get("_keyword",   ""),
            "match_score_preview": job.get("match_score_preview", 0),
            "source":              job.get("_source", "linkedin"),
        }

    # ── Step 6：回填 batch 统计，标记 dedup_done=True
    skipped_analysis = sum(1 for j in display_jobs if j.get("skip_analysis"))
    batch = get_batch(h, batch_id)
    if batch:
        batch["dedup_done"]        = True
        batch["new_total"]         = len(new_jobs)
        batch["displayed"]         = len(display_jobs)
        batch["skipped_duplicate"] = skipped
        batch["hidden_low_score"]  = hidden_count
        batch["skipped_analysis"]  = skipped_analysis
        batch["job_ids"]           = [
            str(j.get("job_id") or j.get("id") or "")
            for j in display_jobs
        ]

    h["seen_jobs"] = seen
    save_history(h)

    return {
        "batch_id":          batch_id,
        "raw_results_file":  str(rp),
        "display_jobs":      display_jobs,
        "total_new":         len(new_jobs),
        "skipped_duplicate": skipped,
        "hidden_low_score":  hidden_count,
        "skipped_analysis":  skipped_analysis,
    }


# ─────────────────────────────────────────────
# 历史摘要
# ─────────────────────────────────────────────

def print_summary():
    h = load_history()
    print(f"累计批次：{len(h['batches'])} 次")
    print(f"累计 seen job_id 数：{len(h['seen_jobs'])} 条\n")

    if not h["batches"]:
        print("  （暂无批次记录）")
        return

    print("最近 5 批：")
    for b in h["batches"][-5:]:
        dedup_flag = "✓" if b.get("dedup_done") else "⚠ 未去重"
        raw_file   = b.get("raw_results_file", "—")
        print(
            f"  {b['batch_id']}  [{dedup_flag}]"
            f"  抓取={b.get('fetched_total', 0)}"
            f"  新增={b.get('new_total') or '—'}"
            f"  展示={b.get('displayed') or '—'}"
            f"  重复={b.get('skipped_duplicate') or '—'}"
        )
        print(f"           原始文件：{raw_file}")


# ─────────────────────────────────────────────
# 入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(_sys.stderr, "reconfigure"):
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="LinkedIn CV Agent — 搜索状态管理"
    )
    parser.add_argument("--mode",
        choices=["offset", "save-raw", "dedup", "summary", "retry-failed"],
        required=True)
    parser.add_argument("--uid",      default="leon", help="用户 ID（对应 users/{uid}/ 目录）")
    parser.add_argument("--config",   default=None,   help="覆盖 config.json 路径")
    parser.add_argument("--batch-id", default=None,
        help="save-raw / dedup / retry-failed 模式必填")
    parser.add_argument("--input",    default=None,
        help="save-raw 模式：原始搜索结果 JSON 文件路径")
    parser.add_argument("--force",    action="store_true",
        help="dedup 模式：即使 dedup_done=true 也强制重跑")
    args = parser.parse_args()
    init_paths(args.uid)

    _base = Path(__file__).resolve().parent.parent / "users" / args.uid
    cfg = {}
    if args.mode in ("offset", "dedup"):
        p = Path(args.config) if args.config else _base / "config.json"
        if not p.exists():
            print(f"ERROR: config 不存在：{p}", file=sys.stderr)
            sys.exit(1)
        cfg = json.loads(p.read_text(encoding="utf-8"))

    if args.mode == "offset":
        print(json.dumps(compute_offsets(cfg), ensure_ascii=False, indent=2))

    elif args.mode == "save-raw":
        if not args.batch_id:
            # 自动生成 batch_id
            h = load_history()
            args.batch_id = new_batch_id(h)
        if not args.input:
            print("ERROR: save-raw 模式需要 --input", file=sys.stderr)
            sys.exit(1)
        raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
        out = save_raw_results(args.batch_id, raw)
        print(json.dumps({
            "batch_id":        args.batch_id,
            "raw_results_file": str(out),
            "fetched_total":   len(raw)
        }, ensure_ascii=False))

    elif args.mode == "dedup":
        if not args.batch_id:
            print("ERROR: dedup 模式需要 --batch-id", file=sys.stderr)
            sys.exit(1)
        # 步骤 2-D：断点续传 — 已完成去重时跳过（除非 --force）
        h = load_history()
        b = get_batch(h, args.batch_id)
        if b and b.get("dedup_done") and not args.force:
            print(f"[skip] {args.batch_id} 已完成去重，使用 --force 强制重跑")
            sys.exit(0)
        result = dedup_and_sort(args.batch_id, cfg)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.mode == "summary":
        print_summary()

    elif args.mode == "retry-failed":
        if not args.batch_id:
            print("ERROR: retry-failed 模式需要 --batch-id", file=sys.stderr)
            sys.exit(1)
        failed = get_failed_jobs(args.batch_id)
        if not failed:
            print(f"[info] {args.batch_id} 无失败任务")
        else:
            print(json.dumps({"batch_id": args.batch_id, "failed_jobs": failed},
                             ensure_ascii=False, indent=2))