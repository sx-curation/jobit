#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_models.py — Sync model IDs from config/model_config.json into
all .claude/agents/*.md frontmatter fields.

Usage:
  python3 scripts/sync_models.py            # apply changes
  python3 scripts/sync_models.py --dry-run  # preview only
"""
import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
AGENTS_DIR  = PROJECT_DIR / '.claude' / 'agents'
CONFIG_PATH = PROJECT_DIR / 'config' / 'model_config.json'


def patch_frontmatter(content: str, new_model: str) -> str:
    """Replace or insert model: line inside YAML frontmatter (first --- block)."""
    if re.search(r'^model:\s*\S', content, re.MULTILINE):
        return re.sub(
            r'^(model:)\s*\S.*$',
            f'model: {new_model}',
            content,
            count=1,
            flags=re.MULTILINE,
        )
    # No model: line yet — insert after opening ---
    return re.sub(r'^(---\n)', f'---\nmodel: {new_model}\n', content, count=1)


def main() -> int:
    ap = argparse.ArgumentParser(description='Sync model IDs into agent frontmatter.')
    ap.add_argument('--dry-run', action='store_true', help='Preview without writing files.')
    args = ap.parse_args()

    if not CONFIG_PATH.exists():
        print(f'ERROR: config not found: {CONFIG_PATH}', file=sys.stderr)
        return 1

    cfg     = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    agents  = cfg.get('agents', {})
    changed = []

    for name, model_id in agents.items():
        md_file = AGENTS_DIR / f'{name}.md'
        if not md_file.exists():
            print(f'  SKIP  {name}.md — file not found')
            continue
        original = md_file.read_text(encoding='utf-8')
        patched  = patch_frontmatter(original, model_id)
        m        = re.search(r'^model:\s*(\S.*)$', original, re.MULTILINE)
        old      = m.group(1).strip() if m else '(none)'
        if patched == original:
            print(f'  OK    {name}.md — {model_id}')
        else:
            print(f'  UPD   {name}.md  {old}  →  {model_id}')
            if not args.dry_run:
                md_file.write_text(patched, encoding='utf-8')
            changed.append(name)

    if args.dry_run:
        suffix = f'  ({len(changed)} file(s) would change)' if changed else '  (nothing to change)'
        print(f'\nDry run complete.{suffix}')
    else:
        print(f'\nDone — {len(changed)} file(s) updated.' if changed else '\nAll agents already match config.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
