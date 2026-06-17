#!/usr/bin/env python3
"""
一次性迁移：将 raw_results_*.json 中 _needs_refetch=True 的 jid
在 seen_jobs 里标记 needs_refetch=True，使前向修复逻辑能在下次搜索时
重新 fetch 并进行 JD 分析。

用法：
  python scripts/backfill_needs_refetch.py --uid leon
  python scripts/backfill_needs_refetch.py --uid leon --since 2025-05-27  # 默认值
  python scripts/backfill_needs_refetch.py --uid leon --dry-run           # 只打印，不写入
"""
import argparse, json, os, sys
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uid",     default="leon")
    parser.add_argument("--since",   default="2025-05-27",
                        help="只处理此日期之后的 raw_results 文件")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base   = Path(__file__).resolve().parent.parent / "users" / args.uid
    temp   = base / "output" / "temp"
    hist_p = base / "output" / "search_history.json"
    cutoff = datetime.fromisoformat(args.since)

    history = json.loads(hist_p.read_text(encoding="utf-8"))
    seen    = history["seen_jobs"]

    # 1. 收集所有 raw_results 中的 needs_refetch jid
    bad_jids: set[str] = set()
    for f in sorted(temp.glob("raw_results_*.json")):
        if datetime.fromtimestamp(f.stat().st_mtime) <= cutoff:
            print(f"  [SKIP older] {f.name}")
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            print(f"  [SKIP parse error] {f.name}: {e}", file=sys.stderr)
            continue
        n = sum(1 for job in data if job.get("_needs_refetch"))
        print(f"  {f.name}: {len(data)} jobs, {n} needs_refetch")
        for job in data:
            if job.get("_needs_refetch"):
                bad_jids.add(str(job["job_id"]))

    print(f"\nbad_jids found in raw_results : {len(bad_jids)}")

    # 2. 在 seen_jobs 里标记
    marked   = 0
    not_seen = 0
    already  = 0
    for jid in bad_jids:
        if jid not in seen:
            not_seen += 1
        elif seen[jid].get("needs_refetch", False):
            already += 1
        else:
            seen[jid]["needs_refetch"] = True
            marked += 1

    print(f"marked in seen_jobs            : {marked}")
    print(f"already marked                 : {already}")
    print(f"not in seen_jobs (ws_ or new)  : {not_seen}")

    if args.dry_run:
        print("\n[dry-run] 未写入，去掉 --dry-run 执行实际写入")
        return

    # 原子写
    tmp = hist_p.with_suffix(".tmp")
    tmp.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, hist_p)
    print(f"\nsearch_history.json updated OK")


if __name__ == "__main__":
    main()
