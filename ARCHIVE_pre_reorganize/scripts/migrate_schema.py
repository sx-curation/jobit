#!/usr/bin/env python3
"""
scripts/migrate_schema.py

将旧版 jd_analysis.json（Leon 的历史数据）迁移到新 schema：
  - match_score  → score
  - _source      → source

默认 dry-run，仅打印变更。加 --apply 才实际写入。

用法：
  python scripts/migrate_schema.py              # dry-run，查看有哪些文件需要迁移
  python scripts/migrate_schema.py --apply      # 实际迁移
  python scripts/migrate_schema.py --uid amy    # 迁移指定用户（默认 leon）
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1] / "1_generate_linkedin_cv"
USERS_DIR   = PROJECT_DIR / "users"


def migrate_file(path: Path, apply: bool) -> bool:
    """返回 True 表示该文件需要（或已经）迁移。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [SKIP] {path.parent.name}: 读取失败 ({e})", file=sys.stderr)
        return False

    changed = False
    changes = []

    # match_score → score
    if "match_score" in data and "score" not in data:
        if apply:
            data["score"] = data.pop("match_score")
        changes.append("match_score → score")
        changed = True

    # _source → source
    if "_source" in data and "source" not in data:
        if apply:
            data["source"] = data.pop("_source")
        changes.append("_source → source")
        changed = True

    if not changed:
        return False

    action = "MIGRATED" if apply else "NEEDS MIGRATION"
    print(f"  [{action}] {path.parent.name}: {', '.join(changes)}")

    if apply:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return True


def main():
    parser = argparse.ArgumentParser(description="Migrate jd_analysis.json schema")
    parser.add_argument("--apply",  action="store_true", help="Actually write changes (default: dry-run)")
    parser.add_argument("--uid",    default="leon",       help="User to migrate (default: leon)")
    args = parser.parse_args()

    output_dir = USERS_DIR / args.uid / "output"
    if not output_dir.exists():
        print(f"ERROR: output dir not found: {output_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(output_dir.glob("*/jd_analysis.json"))
    if not files:
        print(f"No jd_analysis.json files found under {output_dir}")
        return

    mode = "DRY-RUN" if not args.apply else "APPLYING"
    print(f"[{mode}] Scanning {len(files)} files for user '{args.uid}'...\n")

    needs_migration = sum(migrate_file(f, apply=args.apply) for f in files)

    print(f"\nTotal: {needs_migration} / {len(files)} files {'migrated' if args.apply else 'need migration'}.")
    if not args.apply and needs_migration:
        print("Run with --apply to apply changes.")


if __name__ == "__main__":
    main()
