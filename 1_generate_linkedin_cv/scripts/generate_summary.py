#!/usr/bin/env python3
"""
scripts/generate_summary.py

扫描所有 output/*/jd_analysis.json，生成按分数降序排列的汇总表 output/job_summary.md。
每次调用增量更新（覆盖写入，内容始终反映当前所有已完成分析的职缺）。

用法：
  python3 scripts/generate_summary.py
  python3 scripts/generate_summary.py --output output/job_summary.md
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime, timezone


def load_last_seen(output_dir: Path) -> tuple[dict, dict]:
    """Load last_seen dates from search_history.json.
    Returns (job_id → last_seen, (company, title) → last_seen).
    """
    history_file = output_dir / "search_history.json"
    if not history_file.exists():
        return {}, {}
    try:
        seen_jobs = json.loads(history_file.read_text(encoding="utf-8")).get("seen_jobs", {})
    except Exception:
        return {}, {}
    by_id: dict[str, str] = {}
    by_ct: dict[tuple, str] = {}
    for jid, v in seen_jobs.items():
        ls = v.get("last_seen") or v.get("first_seen", "")
        if not ls:
            continue
        by_id[jid] = ls
        ct_key = (v.get("company", "").lower().strip(), v.get("title", "").lower().strip())
        if ct_key[0] and ct_key[1]:
            by_ct[ct_key] = ls
    return by_id, by_ct


def load_all_analyses(output_dir: Path) -> list[dict]:
    """扫描 output/*/jd_analysis.json，返回所有成功解析的记录列表。"""
    last_seen_by_id, last_seen_by_ct = load_last_seen(output_dir)
    records = []
    for analysis_file in sorted(output_dir.glob("*/jd_analysis.json")):
        try:
            with open(analysis_file, encoding="utf-8") as f:
                data = json.load(f)
            # 补充 folder 信息方便调试
            data["_folder"] = analysis_file.parent.name
            # 从文件夹名末尾的 _YYYYMMDD 提取搜索日期（稳定，不受 git clone / copy 影响）
            # 降级：找不到时才用 st_ctime（创建时间）
            # 注意：不用 st_mtime，因为写入 application_record 等操作会更新 mtime 导致日期漂移
            folder_name = analysis_file.parent.name
            date_match = re.search(r"_(\d{8})$", folder_name)
            if date_match:
                d = date_match.group(1)
                data["_analyzed_date"] = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            else:
                data["_analyzed_date"] = datetime.fromtimestamp(
                    analysis_file.stat().st_ctime
                ).strftime("%Y-%m-%d")
            # 从 search_history.json 关联 last_seen
            jid = str(data.get("job_id") or "")
            ct_key = (data.get("company", "").lower().strip(), data.get("title", "").lower().strip())
            data["_last_seen"] = last_seen_by_id.get(jid) or last_seen_by_ct.get(ct_key) or ""
            records.append(data)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] 跳过 {analysis_file}: {e}", file=sys.stderr)
    return records


def cross_source_dedup(records: list[dict]) -> list[dict]:
    """
    Dedup by (company, title) case-insensitively across sources and batches.
    For any group of duplicates, always use the earliest _analyzed_date.
    When the same job appears on both LinkedIn and Stepstone:
      - Keep the LinkedIn record
      - Fill missing URL from Stepstone
      - Set _remark = '数据源重复'
    Same-source cross-batch duplicates: keep the highest-scoring record.
    """
    from collections import defaultdict

    key_map: dict = defaultdict(list)
    for r in records:
        key = (
            r.get("company", "").strip().lower(),
            r.get("title",   "").strip().lower(),
        )
        key_map[key].append(r)

    result = []
    for group in key_map.values():
        if len(group) == 1:
            result.append(group[0])
            continue

        all_dates = [r.get("_analyzed_date", "") for r in group if r.get("_analyzed_date")]
        earliest = min(all_dates) if all_dates else None

        linkedin_recs  = [r for r in group if r.get("_source", "linkedin") != "stepstone"]
        stepstone_recs = [r for r in group if r.get("_source", "") == "stepstone"]

        if linkedin_recs and stepstone_recs:
            kept = linkedin_recs[0]
            if not kept.get("url") and stepstone_recs[0].get("url"):
                kept["url"] = stepstone_recs[0]["url"]
            kept["_remark"] = "数据源重复"
        else:
            kept = max(group, key=lambda r: r.get("match_score", 0))

        if earliest:
            kept["_analyzed_date"] = earliest
        result.append(kept)

    return result


def extract_group_id(folder: str) -> str:
    """从文件夹名称动态提取 group-id（取首个下划线前的 group- 前缀）。"""
    if folder.startswith("group-"):
        return folder.split("_")[0]
    return "—"


def fmt_list(items: list[str], max_items: int = 3) -> str:
    """将列表格式化为分号分隔字符串，超出 max_items 时追加 +N。"""
    if not items:
        return "—"
    shown = items[:max_items]
    rest = len(items) - max_items
    # 用分号分隔，避免逗号与 Markdown 表格混淆
    def _to_str(s):
        if isinstance(s, dict):
            return s.get("skill") or s.get("name") or str(s)
        return str(s)
    result = "; ".join(_to_str(s).replace("|", "/") for s in shown)
    if rest > 0:
        result += f" +{rest}"
    return result


def score_bar(score: int) -> str:
    """用 emoji 色块直观显示分数段。"""
    if score >= 75:
        return "🟢"
    if score >= 60:
        return "🟡"
    if score >= 45:
        return "🟠"
    return "🔴"


def build_markdown(records: list[dict]) -> str:
    """根据记录列表生成 Markdown 汇总表（列顺序按 Orchestrator.md 规范）。"""
    # 按 match_score 降序排序
    records_sorted = sorted(records, key=lambda r: r.get("match_score", 0), reverse=True)

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Job Analysis Summary",
        "",
        f"_Last updated: {now} — {len(records_sorted)} jobs analyzed_",
        "",
        "| # | Score | Group | Source | Company | Title | Size | URL | Recommended Emphasis | Missing Skills | Analyzed | Last Seen | Remark |",
        "|---|-------|-------|--------|---------|-------|------|-----|----------------------|----------------|----------|-----------|--------|",
    ]

    SOURCE_LABEL = {"linkedin": "LinkedIn", "stepstone": "Stepstone"}

    for i, rec in enumerate(records_sorted, 1):
        score = rec.get("match_score", 0)
        company = rec.get("company", "—").replace("|", "/")
        title = rec.get("title", "—").replace("|", "/")
        url = rec.get("url", "")
        folder = rec.get("_folder", "")
        group_id = extract_group_id(folder)
        analyzed  = rec.get("_analyzed_date", "—")
        last_seen = rec.get("_last_seen", "") or "—"
        source = SOURCE_LABEL.get(rec.get("_source", "linkedin"), "LinkedIn")

        size_info = rec.get("company_info") or {}
        size = size_info.get("size") or "—"

        emphasis = rec.get("recommended_emphasis") or []
        missing = rec.get("missing_skills") or []

        url_cell = f"[Link]({url})" if url else "—"
        bar = score_bar(score)
        score_cell = f"{bar} [**{score}**]({folder}/jd_analysis.json)" if folder else f"{bar} **{score}**"

        lines.append(
            f"| {i} | {score_cell} | {group_id} | {source} | {company} | {title} | {size} "
            f"| {url_cell} | {fmt_list(emphasis)} | {fmt_list(missing)} | {analyzed} | {last_seen} | {rec.get('_remark', '')} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("_Scores: 🟢 ≥75  🟡 60-74  🟠 45-59  🔴 <45_")
    lines.append("")

    return "\n".join(lines)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="生成职缺分析汇总表")
    parser.add_argument(
        "--uid",
        default="leon",
        help="用户 ID（对应 users/{uid}/ 目录）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出 Markdown 文件路径（默认 users/{uid}/output/job_summary.md）",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="扫描目录（默认 users/{uid}/output）",
    )
    args = parser.parse_args()

    _base      = Path(__file__).resolve().parent.parent / "users" / args.uid
    output_dir = Path(args.output_dir) if args.output_dir else _base / "output"
    if not output_dir.exists():
        print(f"[ERROR] 输出目录不存在: {output_dir}", file=sys.stderr)
        sys.exit(1)

    records = load_all_analyses(output_dir)
    if not records:
        print("[WARN] 未找到任何 jd_analysis.json，不生成汇总表。", file=sys.stderr)
        sys.exit(0)

    records = cross_source_dedup(records)
    md = build_markdown(records)

    out_path = Path(args.output) if args.output else output_dir / "job_summary.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: write to .tmp then rename to prevent corrupt file on crash
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(md, encoding="utf-8")
    os.replace(tmp, out_path)

    print(f"SUMMARY_OK: {out_path} ({len(records)} jobs)")


if __name__ == "__main__":
    main()
