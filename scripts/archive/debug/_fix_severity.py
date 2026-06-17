"""
_fix_severity.py — 一次性脚本
将 missing_skills 为纯字符串的 jd_analysis.json 升级为 M5 对象格式。
通过原始 JD 文本（raw_results）中的上下文关键词判断 severity。

用法：
  py scripts/_fix_severity.py --user leon
"""

import json
import re
import sys
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

HARD_BLOCKER_KEYWORDS = [
    'required', 'must have', 'must-have', 'zwingend', 'erforderlich',
    'voraussetzung', 'unbedingt', 'obligatory', 'mandatory',
]
NICE_TO_HAVE_KEYWORDS = [
    'preferred', 'nice to have', 'nice-to-have', 'von vorteil', 'wünschenswert',
    'ideally', 'ideal', 'plus', 'bonus', 'advantageous', 'desirable',
    'beneficial', 'welcome',
]

WEEKS_DEFAULTS = {
    'hard_blocker': None,
    'nice_to_have': 6,
    'learnable': 3,
}


def load_json(path: Path):
    for enc in ('utf-8', 'utf-8-sig'):
        try:
            return json.loads(path.read_text(encoding=enc))
        except Exception:
            continue
    return None


def classify_skill_in_jd(skill_str: str, jd_text: str) -> str:
    """Use JD context around skill keywords to determine severity."""
    # First: check the skill string itself for embedded severity markers
    skill_lower = skill_str.lower()
    if any(kw in skill_lower for kw in HARD_BLOCKER_KEYWORDS):
        return 'hard_blocker'
    if any(kw in skill_lower for kw in NICE_TO_HAVE_KEYWORDS):
        return 'nice_to_have'

    if not jd_text:
        return 'learnable'

    # Extract meaningful words from the skill string (len >= 4)
    key_words = [w for w in re.findall(r'[A-Za-zÄÖÜäöü]{4,}', skill_str)][:4]
    if not key_words:
        return 'learnable'

    jd_lower = jd_text.lower()
    best = 'learnable'

    for word in key_words:
        for m in re.finditer(re.escape(word.lower()), jd_lower):
            # ±300 chars context
            ctx = jd_lower[max(0, m.start() - 300): m.end() + 300]
            if any(kw in ctx for kw in HARD_BLOCKER_KEYWORDS):
                return 'hard_blocker'  # immediate return on hard blocker
            if any(kw in ctx for kw in NICE_TO_HAVE_KEYWORDS):
                best = 'nice_to_have'

    return best


def build_skill_object(skill_str: str, severity: str) -> dict:
    return {
        'skill': skill_str,
        'severity': severity,
        'weeks_to_acquire': WEEKS_DEFAULTS[severity],
        'adjacent_in_cv': None,
        'mitigation': None,
    }


def build_gap_summary(skill_objects: list) -> dict:
    counts = {'hard_blocker': 0, 'nice_to_have': 0, 'learnable': 0}
    for s in skill_objects:
        sev = s.get('severity', 'learnable')
        if sev in counts:
            counts[sev] += 1
        else:
            counts['learnable'] += 1
    return {
        'hard_blockers': counts['hard_blocker'],
        'nice_to_have': counts['nice_to_have'],
        'learnable': counts['learnable'],
        'blocker_flag': counts['hard_blocker'] > 0,
    }


def fix_user(user_dir: Path, dry_run: bool = False):
    temp_dir = user_dir / 'output' / 'temp'
    output_dir = user_dir / 'output'

    # Build job_id → raw entry lookup
    raw_lookup: dict = {}
    for f in sorted(temp_dir.glob('raw_results_*.json')):
        data = load_json(f)
        if not isinstance(data, list):
            continue
        for job in data:
            jid = str(job.get('job_id', ''))
            if jid and jid not in raw_lookup:
                raw_lookup[jid] = job
    print(f'  Raw lookup: {len(raw_lookup)} entries')

    fixed = 0
    skipped_already_ok = 0
    skipped_no_jd = 0

    for job_folder in sorted(output_dir.iterdir()):
        if not job_folder.is_dir() or job_folder.name == 'temp':
            continue
        jda_path = job_folder / 'jd_analysis.json'
        if not jda_path.exists():
            continue

        data = load_json(jda_path)
        if not isinstance(data, dict):
            continue

        ms = data.get('missing_skills', [])
        if not ms:
            continue

        # Already M5 format?
        if isinstance(ms[0], dict):
            skipped_already_ok += 1
            # Ensure gap_summary exists even for already-M5 files
            if not data.get('gap_summary'):
                data['gap_summary'] = build_gap_summary(ms)
                if not dry_run:
                    jda_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            continue

        # Get JD text
        job_id = str(data.get('job_id', ''))
        raw = raw_lookup.get(job_id, {})
        jd_text = raw.get('description_full', '')

        if not jd_text:
            skipped_no_jd += 1
            # Fall back: classify all as learnable (no JD context)
            skill_objects = [build_skill_object(s, 'learnable') for s in ms if isinstance(s, str)]
        else:
            skill_objects = []
            for s in ms:
                if not isinstance(s, str):
                    skill_objects.append(s)
                    continue
                sev = classify_skill_in_jd(s, jd_text)
                skill_objects.append(build_skill_object(s, sev))

        data['missing_skills'] = skill_objects
        data['gap_summary'] = build_gap_summary(skill_objects)

        if not dry_run:
            jda_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        fixed += 1

    print(f'  Fixed: {fixed}  |  Already M5: {skipped_already_ok}  |  No JD text (fallback=learnable): {skipped_no_jd}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--user', help='User name (e.g. leon)')
    parser.add_argument('--all-users', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    users_dir = BASE_DIR / 'users'
    if args.all_users:
        users = [d for d in users_dir.iterdir() if d.is_dir()]
    elif args.user:
        users = [users_dir / args.user]
    else:
        print('specify --user <name> or --all-users')
        sys.exit(1)

    for user_dir in users:
        if not user_dir.exists():
            print(f'Not found: {user_dir}')
            continue
        print(f'\n=== Fix severity for: {user_dir.name} ===')
        fix_user(user_dir, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
