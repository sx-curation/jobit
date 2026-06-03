"""
backfill_decision_score.py
为所有 jd_analysis.json 中缺失 decision_score（== -1 或 None）的职位，
从 output/temp/raw_results_*.json 数据 + config.json 用户偏好计算并回填。

用法：
  py scripts/backfill_decision_score.py --user leon
  py scripts/backfill_decision_score.py --all-users
"""

import json
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent  # 1_generate_linkedin_cv/

# ── decision_score formula weights ────────────────────────────────────────────
WEIGHTS = {
    'level_fit':           0.25,
    'location_fit':        0.20,
    'work_mode_fit':       0.15,
    'posting_freshness':   0.05,
    'compensation_fit':    0.10,
    'job_family_fit':      0.15,
    'company_culture_fit': 0.10,
}


def load_json(path: Path) -> dict | list | None:
    for enc in ('utf-8', 'utf-8-sig'):
        try:
            return json.loads(path.read_text(encoding=enc))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return None


def build_raw_lookup(temp_dir: Path) -> dict:
    """job_id -> raw job entry from raw_results_*.json files."""
    lookup = {}
    for f in sorted(temp_dir.glob('raw_results_*.json')):
        data = load_json(f)
        if not isinstance(data, list):
            continue
        for job in data:
            jid = str(job.get('job_id', ''))
            if jid and jid not in lookup:
                lookup[jid] = job
    return lookup


def calc_level_fit(title: str) -> int:
    title_lower = title.lower()
    if any(w in title_lower for w in ['senior', 'lead', 'head of', 'director', 'vp ']):
        return 65  # above target level, slight penalty
    if any(w in title_lower for w in ['manager', 'specialist', 'analyst', 'consultant', 'coordinator', 'officer', 'advisor']):
        return 80
    if any(w in title_lower for w in ['junior', 'intern', 'trainee', 'werkstudent']):
        return 40
    return 65


def calc_location_fit(location: str, preferred_locations: list[str]) -> int:
    if not location:
        return 60
    loc_lower = location.lower()
    for pref in preferred_locations:
        if pref.lower() in loc_lower:
            return 100
    if any(w in loc_lower for w in ['germany', 'deutschland', 'remote', 'hybrid']):
        return 70
    if any(w in loc_lower for w in ['european', 'eu ', 'europe']):
        return 50
    return 30


def calc_work_mode_fit(description: str, preferred_modes: list[str]) -> int:
    if not description:
        return 70
    desc_lower = description.lower()
    user_prefers_remote = any(m.lower() in ('remote', 'fully remote') for m in preferred_modes)
    user_prefers_hybrid = any(m.lower() == 'hybrid' for m in preferred_modes)

    has_remote = any(w in desc_lower for w in ['fully remote', 'remote-first', '100% remote', 'work from anywhere'])
    has_hybrid = any(w in desc_lower for w in ['hybrid', 'homeoffice', 'home office', 'remote possible', 'remote option'])
    has_onsite = any(w in desc_lower for w in ['vor ort', 'on-site only', 'onsite only', 'in-office'])

    if has_remote and (user_prefers_remote or user_prefers_hybrid):
        return 100
    if has_hybrid and (user_prefers_hybrid or user_prefers_remote):
        return 85
    if has_onsite and not has_hybrid:
        return 40
    # No clear signal
    return 70


def calc_posting_freshness(out_dir_name: str) -> int:
    """Extract YYYYMMDD from folder name and compute days since posting."""
    match = re.search(r'_(\d{8})$', out_dir_name)
    if not match:
        return 80  # default if no date found
    try:
        batch_date = datetime.strptime(match.group(1), '%Y%m%d')
        days_old = (datetime.now() - batch_date).days
        if days_old <= 7:
            return 100
        elif days_old <= 14:
            return 85
        elif days_old <= 30:
            return 65
        elif days_old <= 60:
            return 45
        else:
            return 25
    except ValueError:
        return 80


def calc_job_family_fit(group_id: str, enabled_groups: list[str]) -> int:
    if not group_id:
        return 65
    if group_id in enabled_groups:
        return 85
    return 55


def calc_decision_score(signals: dict) -> int:
    total = sum(signals.get(k, 50) * w for k, w in WEIGHTS.items())
    return round(total)


def backfill_user(user_dir: Path):
    config_path = user_dir / 'config.json'
    if not config_path.exists():
        print(f'  SKIP: no config.json in {user_dir}')
        return

    config = load_json(config_path)
    if not config:
        print(f'  SKIP: cannot parse config.json')
        return

    preferred_locations = config.get('preferred_locations', [])
    preferred_work_modes = config.get('work_mode', [])
    if isinstance(preferred_work_modes, str):
        preferred_work_modes = [preferred_work_modes]
    enabled_groups = list(config.get('keyword_groups', {}).keys())

    temp_dir = user_dir / 'output' / 'temp'
    raw_lookup = build_raw_lookup(temp_dir)
    print(f'  Raw lookup: {len(raw_lookup)} unique job_ids')

    output_dir = user_dir / 'output'
    updated = 0
    skipped_existing = 0
    skipped_no_raw = 0

    for job_folder in sorted(output_dir.iterdir()):
        if not job_folder.is_dir() or job_folder.name == 'temp':
            continue
        jda_path = job_folder / 'jd_analysis.json'
        if not jda_path.exists():
            continue

        data = load_json(jda_path)
        if not isinstance(data, dict):
            continue

        # Skip if already has valid decision_score
        existing_ds = data.get('decision_score', -1)
        if existing_ds is not None and existing_ds not in (-1, 0):
            skipped_existing += 1
            continue

        # Find raw job data
        job_id = str(data.get('job_id', ''))
        raw = raw_lookup.get(job_id, {})

        group_id = raw.get('_group_id', '')
        location = raw.get('location', '')
        description = raw.get('description_full', '')

        if not group_id:
            # Try to infer group from folder name
            folder_name = job_folder.name
            for g in enabled_groups:
                if folder_name.startswith(g):
                    group_id = g
                    break

        if not raw and not group_id:
            skipped_no_raw += 1
            continue

        title = data.get('title', '')
        signals = {
            'level_fit':           calc_level_fit(title),
            'location_fit':        calc_location_fit(location, preferred_locations),
            'work_mode_fit':       calc_work_mode_fit(description, preferred_work_modes),
            'posting_freshness':   calc_posting_freshness(job_folder.name),
            'compensation_fit':    50,   # no salary data until M6
            'job_family_fit':      calc_job_family_fit(group_id, enabled_groups),
            'company_culture_fit': 50,   # no kununu data until M6
        }
        ds = calc_decision_score(signals)

        data['decision_score'] = ds
        data['decision_signals'] = signals
        if 'decision_notes' not in data:
            data['decision_notes'] = ['backfilled from raw_results; compensation_fit and company_culture_fit use default 50']

        jda_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        updated += 1

    print(f'  Updated: {updated}  |  Already had decision_score: {skipped_existing}  |  No raw data: {skipped_no_raw}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--user', help='User directory name (e.g. leon)')
    parser.add_argument('--all-users', action='store_true')
    args = parser.parse_args()

    users_dir = BASE_DIR / 'users'

    if args.all_users:
        users = [d for d in users_dir.iterdir() if d.is_dir()]
    elif args.user:
        users = [users_dir / args.user]
    else:
        print('ERROR: specify --user <name> or --all-users')
        sys.exit(1)

    for user_dir in users:
        if not user_dir.exists():
            print(f'User dir not found: {user_dir}')
            continue
        print(f'\n=== Backfilling decision_score for user: {user_dir.name} ===')
        backfill_user(user_dir)


if __name__ == '__main__':
    main()
