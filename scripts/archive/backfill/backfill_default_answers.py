"""
backfill_default_answers.py
为所有 match_score >= 70 且缺少 default_answers 的职缺，
调用 default-answers agent 生成面试答案并写入 jd_analysis.json。

用法：
  python scripts/backfill_default_answers.py --user leon
  python scripts/backfill_default_answers.py --all-users
  python scripts/backfill_default_answers.py --user leon --dry-run
"""

import json
import re
import sys
import argparse
import shutil
import subprocess
import threading
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent  # 1_generate_linkedin_cv/
USERS_DIR = BASE_DIR / 'users'
SCORE_THRESHOLD = 70
MAX_WORKERS = 3


def _extract_qa(_re, text: str) -> list:
    """Parse Q&A from JSON or markdown (## Q<n> / **A:**) format."""
    try:
        clean = _re.sub(r'```(?:json)?\s*|\s*```', '', text)
        m = _re.search(r'\{"default_answers"\s*:\s*\[[\s\S]*?\]\s*\}', clean)
        if m:
            parsed = json.loads(m.group())
            if parsed.get('default_answers'):
                return parsed['default_answers']
    except Exception:
        pass
    pairs = []
    parts = _re.split(r'(?m)^##\s+Q\d+\s*', text)
    for part in parts[1:]:
        lines = part.strip().split('\n')
        q = _re.sub(r'^[^\w]*', '', lines[0]).strip()
        rest = '\n'.join(lines[1:])
        a_match = _re.search(r'\*\*A(?:nswer)?:\*\*\s*([\s\S]+)', rest)
        if not a_match:
            continue
        a_raw = a_match.group(1).strip()
        a_raw = _re.sub(r'\*\*(.*?)\*\*', r'\1', a_raw)
        a_raw = _re.sub(r'\*(.*?)\*', r'\1', a_raw)
        a_raw = _re.sub(r'^[-—]+$', '', a_raw, flags=_re.MULTILINE)
        a_clean = _re.sub(r'\s+', ' ', a_raw).strip()
        if q and a_clean:
            pairs.append({'question': q, 'answer': a_clean})
    return pairs[:5]


def load_json(path: Path):
    for enc in ('utf-8', 'utf-8-sig'):
        try:
            return json.loads(path.read_text(encoding=enc))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return None


def needs_answers(jd_path: Path) -> bool:
    """Return True if jd_analysis.json has match_score >= 70 and no default_answers."""
    data = load_json(jd_path)
    if not isinstance(data, dict):
        return False
    score = data.get('match_score')
    if score is None or float(score) < SCORE_THRESHOLD:
        return False
    answers = data.get('default_answers')
    return not answers  # missing or empty list


def collect_targets(uid: str) -> list[tuple[str, Path]]:
    """Return list of (job_folder_name, jd_analysis_path) needing backfill."""
    output_dir = USERS_DIR / uid / 'output'
    if not output_dir.exists():
        return []
    targets = []
    for jd_path in sorted(output_dir.glob('*/jd_analysis.json')):
        if needs_answers(jd_path):
            targets.append((jd_path.parent.name, jd_path))
    return targets


def run_agent(uid: str, job_folder: str, user_dir: Path, results: list, lock: threading.Lock):
    claude_bin = shutil.which('claude')
    if not claude_bin:
        with lock:
            print('ERROR: claude binary not found. Ensure claude CLI is installed and in PATH.')
        sys.exit(1)

    jd_file = user_dir / 'output' / job_folder / 'jd_analysis.json'
    jd = load_json(jd_file) or {}
    company     = jd.get('company', '')
    title       = jd.get('title', '')
    cores       = jd.get('core_responsibilities', [])[:5]
    matched     = jd.get('matched_skills', [])[:8]
    cores_str   = '\n'.join(
        f'- {r.get("responsibility", r) if isinstance(r, dict) else r}' for r in cores)
    matched_str = ', '.join(
        (m if isinstance(m, str) else m.get('skill', '')) for m in matched)
    prompt = (
        f'Generate exactly 5 common interview Q&A for the role: {title} at {company}.\n'
        f'Core responsibilities:\n{cores_str}\n'
        f'Candidate matched skills: {matched_str}\n'
        'Write answers in first person, 3-5 sentences each. English only.\n'
        'Output ONLY valid JSON, no markdown, no code fences, no extra text:\n'
        '{"default_answers":[{"question":"...","answer":"..."}]}'
    )

    ok = False
    try:
        proc = subprocess.run(
            [claude_bin, '-p', prompt],
            cwd=str(user_dir),
            capture_output=True, text=True,
            encoding='utf-8', errors='replace',
            timeout=180,
        )
        if proc.returncode == 0 and proc.stdout:
            answers = _extract_qa(re, proc.stdout)
            if answers:
                detail = load_json(jd_file) or {}
                detail['default_answers'] = answers
                jd_file.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding='utf-8')
                ok = True
    except subprocess.TimeoutExpired:
        ok = False
    except Exception as exc:
        with lock:
            print(f'  WARN {job_folder}: {exc}')

    with lock:
        status = 'OK  ' if ok else 'FAIL'
        print(f'  [{status}] {job_folder}')
        results.append((job_folder, ok))


def backfill_user(uid: str, dry_run: bool):
    targets = collect_targets(uid)
    if not targets:
        print(f'[{uid}] No jobs need backfill (all 70+ jobs already have default_answers).')
        return

    print(f'[{uid}] {len(targets)} job(s) to backfill:')
    for name, _ in targets:
        print(f'  - {name}')

    if dry_run:
        print('  (dry-run mode - skipping execution)')
        return

    user_dir = USERS_DIR / uid
    results = []
    lock = threading.Lock()
    sem = threading.Semaphore(MAX_WORKERS)

    def worker(job_folder, jd_path):
        with sem:
            run_agent(uid, job_folder, user_dir, results, lock)

    threads = [
        threading.Thread(target=worker, args=(name, path), daemon=True)
        for name, path in targets
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok_count = sum(1 for _, ok in results if ok)
    print(f'\n[{uid}] Done — {ok_count}/{len(targets)} succeeded.')


def main():
    parser = argparse.ArgumentParser(description='Backfill default_answers for 70+ score jobs.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--user', metavar='UID', help='Single user ID to process')
    group.add_argument('--all-users', action='store_true', help='Process all users in users/')
    parser.add_argument('--dry-run', action='store_true', help='List targets without running')
    args = parser.parse_args()

    if args.all_users:
        uids = [d.name for d in sorted(USERS_DIR.iterdir()) if d.is_dir()]
    else:
        uids = [args.user]

    for uid in uids:
        backfill_user(uid, args.dry_run)


if __name__ == '__main__':
    main()
