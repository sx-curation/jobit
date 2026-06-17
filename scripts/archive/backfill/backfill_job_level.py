"""
scripts/backfill_job_level.py
为所有 jd_analysis.json 回填 job_level 字段（本地 regex，无 LLM 调用）。

用法：
  py scripts/backfill_job_level.py --user leon
  py scripts/backfill_job_level.py --all-users
  py scripts/backfill_job_level.py --user leon --force   # 强制覆盖已有值
"""
import json, sys, argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Import get_job_level from sibling module
sys.path.insert(0, str(Path(__file__).parent))
from backfill_decision_score import get_job_level


def backfill_user(user_dir: Path, force: bool = False):
    output_dir = user_dir / 'output'
    if not output_dir.exists():
        print(f'  SKIP: output dir missing for {user_dir.name}')
        return
    updated = skipped = errors = 0
    for jda_path in sorted(output_dir.glob('*/jd_analysis.json')):
        try:
            data = json.loads(jda_path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'  ERROR {jda_path.parent.name}: {e}', file=sys.stderr)
            errors += 1
            continue
        if 'job_level' in data and not force:
            skipped += 1
            continue
        title = data.get('title', '')
        data['job_level'] = get_job_level(title)
        jda_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        updated += 1
    print(f'  {user_dir.name}: updated={updated}  already_set={skipped}  errors={errors}')


def main():
    parser = argparse.ArgumentParser(description='Backfill job_level in jd_analysis.json')
    parser.add_argument('--user', help='User directory name (e.g. leon)')
    parser.add_argument('--all-users', action='store_true')
    parser.add_argument('--force', action='store_true', help='Overwrite existing job_level values')
    args = parser.parse_args()

    users_dir = BASE_DIR / 'users'

    if args.all_users:
        users = [d for d in users_dir.iterdir() if d.is_dir()]
    elif args.user:
        users = [users_dir / args.user]
    else:
        print('ERROR: specify --user <name> or --all-users')
        sys.exit(1)

    for ud in users:
        if not ud.exists():
            print(f'  User dir not found: {ud}')
            continue
        backfill_user(ud, force=args.force)


if __name__ == '__main__':
    main()
