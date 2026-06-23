#!/usr/bin/env python3
"""
scripts/pre_generate.py

为 JD Fit >= min_score 的职缺预生成：
  1. AI Enhanced desc_full (exp_optimized, Workday ATS)
  2. 5 大默认面试答案 (default_answers)
并缓存到各职缺的 jd_analysis.json。

用法（在项目根目录运行）：
  python scripts/pre_generate.py --uid leon
  python scripts/pre_generate.py --uid leon --batch-id 20260602_001
  python scripts/pre_generate.py --uid leon --min-score 70
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import anthropic as _anthropic_mod
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8-sig', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8-sig', errors='replace')

DEFAULT_MIN_SCORE = 70
MAX_WORKERS       = 2
CLAUDE_TIMEOUT    = 300  # seconds per Claude call


def _user_dir(uid: str) -> Path:
    return Path('users') / uid


def load_history(uid: str) -> dict:
    h = _user_dir(uid) / 'output' / 'search_history.json'
    if not h.exists():
        return {}
    return json.loads(h.read_text(encoding='utf-8-sig'))


def find_high_score_jobs(uid: str, batch_id: str | None, min_score: int) -> list[tuple[str, str]]:
    """Return [(job_folder, group_id), ...] for jobs with match_score >= min_score."""
    output_dir = _user_dir(uid) / 'output'
    if not output_dir.exists():
        print(f'[WARN] output dir not found: {output_dir}', file=sys.stderr)
        return []

    results = []
    for jd_file in output_dir.rglob('jd_analysis.json'):
        job_folder = jd_file.parent.name
        # batch filter: if batch_id given, folder must start with a job_id from that batch
        if batch_id:
            h = load_history(uid)
            batch = next((b for b in h.get('batches', []) if b.get('batch_id') == batch_id), None)
            if batch:
                ids = set(str(i) for i in batch.get('job_ids', []))
                # job_folder contains job_id as part of its name only if it was created from this batch
                # Approximate: check if folder date matches batch date
                batch_date = batch_id[:8]
                if not job_folder.endswith(f'_{batch_date}'):
                    continue

        try:
            jd = json.loads(jd_file.read_text(encoding='utf-8-sig'))
        except Exception:
            continue

        score = jd.get('match_score', 0) or 0
        if score < min_score:
            continue

        group_id = job_folder.split('_')[0]
        results.append((job_folder, group_id))

    return results


def run_claude(prompt: str, cwd: Path) -> str:
    """Run claude -p from a neutral directory (no CLAUDE.md) to avoid project context interference."""
    import tempfile
    claude_bin = shutil.which('claude') or 'claude'
    neutral_cwd = Path(tempfile.gettempdir())
    try:
        result = subprocess.run(
            [claude_bin, '-p', prompt],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(neutral_cwd),
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=CLAUDE_TIMEOUT,
        )
        return result.stdout or ''
    except subprocess.TimeoutExpired:
        return ''
    except Exception as e:
        print(f'  [ERROR] claude call failed: {e}', file=sys.stderr)
        return ''


def run_api(system: str, user: str) -> str:
    """Call Anthropic API if key available, otherwise return empty (triggers Python fallback)."""
    if not _ANTHROPIC_AVAILABLE:
        return ''
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return ''
    try:
        client = _anthropic_mod.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model='claude-sonnet-4-6-20251001',
            max_tokens=2048,
            system=system,
            messages=[{'role': 'user', 'content': user}],
        )
        return msg.content[0].text if msg.content else ''
    except Exception as e:
        print(f'  [ERROR] API call failed: {e}', file=sys.stderr)
        return ''


def _template_default_answers(jd: dict, cv: dict) -> list[dict]:
    """Generate template-based interview answers from jd + cv data (no LLM required)."""
    company   = jd.get('company', 'the company')
    title     = jd.get('title', 'this role')
    culture   = (jd.get('culture_keywords') or [])[:3]
    skills    = (jd.get('matched_skills') or [])[:3]
    core_r    = (jd.get('core_responsibilities') or [])[:2]

    # Pick top 2 experiences from cv
    exps = cv.get('experience', [])[:2]
    exp1 = exps[0] if exps else {}
    exp2 = exps[1] if len(exps) > 1 else exp1

    co1   = exp1.get('company', 'my previous role')
    ttl1  = exp1.get('title', '')
    co2   = exp2.get('company', co1)
    ttl2  = exp2.get('title', ttl1)
    b1    = (exp1.get('bullets') or [''])[0][:120]
    skill1 = skills[0] if skills else 'analytical thinking'
    skill2 = skills[1] if len(skills) > 1 else 'strategic planning'
    cult1 = culture[0] if culture else 'innovation'
    core1 = core_r[0][:100] if core_r else 'delivering impactful results'

    return [
        {
            'question': f'Why do you want to work at {company}?',
            'answer': (
                f"I'm excited about {company}'s focus on {cult1} and the opportunity to contribute to "
                f"{core1.rstrip('.')}. My experience at {co1} in {skill1} aligns directly with this role's "
                f"requirements, and I'm drawn to {company}'s mission and growth trajectory."
            )
        },
        {
            'question': 'What is your greatest professional strength?',
            'answer': (
                f"My greatest strength is {skill1}, backed by hands-on experience at {co1} where I {b1.rstrip('.')}. "
                f"I also excel at {skill2}, which I've applied across multiple markets to drive measurable results."
            )
        },
        {
            'question': 'Walk me through your most relevant project or achievement.',
            'answer': (
                f"At {co1} as {ttl1}, I focused on {skill1} and {skill2}. {b1.rstrip('.')}. "
                f"This experience directly shaped my approach to {core1.rstrip('.')} — "
                f"exactly what the {title} role requires."
            )
        },
        {
            'question': f'How does your background prepare you for the {title} role?',
            'answer': (
                f"My roles at {co1} and {co2} provided direct experience in {skill1} and {skill2}. "
                f"At {co2} as {ttl2}, I developed skills in stakeholder alignment and cross-functional delivery. "
                f"Combined, these prepare me to immediately contribute to {company}'s goals in this role."
            )
        },
        {
            'question': 'Where do you see yourself in the next 3-5 years?',
            'answer': (
                f"I aim to deepen my expertise in {skill1} and take on greater ownership of {core1.rstrip('.')} "
                f"at {company}. Long-term, I see myself growing into a senior leadership role where I can "
                f"mentor others and drive {cult1}-focused initiatives at scale."
            )
        },
    ]


def process_job(job_folder: str, group_id: str, uid: str) -> str:
    user_dir  = _user_dir(uid)
    jd_path   = user_dir / 'output' / job_folder / 'jd_analysis.json'
    if not jd_path.exists():
        return f'SKIP {job_folder}: no jd_analysis.json'

    try:
        jd = json.loads(jd_path.read_text(encoding='utf-8-sig'))
    except Exception as e:
        return f'ERROR {job_folder}: {e}'

    changed = False

    # ── 1. exp_optimized ──────────────────────────────────────────────────────
    if not jd.get('exp_optimized'):
        cv_path = user_dir / 'output' / f'cv_parsed_{group_id}.json'
        if cv_path.exists():
            try:
                cv = json.loads(cv_path.read_text(encoding='utf-8-sig'))
                optimized = {}
                # Read JD context for optimization
                matched_skills = jd.get('matched_skills', [])
                recommended_emphasis = jd.get('recommended_emphasis', [])
                skills_str = ', '.join(matched_skills[:10])
                emphasis_str = '\n'.join(f'- {e}' for e in recommended_emphasis[:3])

                for exp in cv.get('experience', []):
                    company = (exp.get('company') or '').strip()
                    bullets = exp.get('bullets', [])
                    if not company or not bullets:
                        continue
                    desc = '\n'.join(f'- {b}' for b in bullets)
                    system_exp = (
                        'You are an ATS resume optimization expert. '
                        'Rewrite work experience bullets following these rules STRICTLY:\n'
                        '1. Only use content from the provided bullets — no fabrication\n'
                        '2. Put the most JD-relevant bullet first\n'
                        '3. Inject at most 2 JD keywords naturally (rephrase, do not add new facts)\n'
                        '4. Remove clichés: leveraged, facilitated, synergies, spearheaded\n'
                        '5. Use varied action verbs, avoid repeating managed/led\n'
                        '6. Preserve all numbers and metrics exactly\n'
                        'Output ONLY the rewritten bullets, one per line starting with a verb. '
                        'No headers, no explanation, no markdown.'
                    )
                    user_exp = (
                        f'Rewrite for role: {jd.get("title","")} at {jd.get("company","")}\n\n'
                        f'JD matched skills: {skills_str}\n\n'
                        f'Recommended emphasis:\n{emphasis_str}\n\n'
                        f'Original bullets for {company}:\n{desc}'
                    )
                    out = run_api(system_exp, user_exp).strip()
                    if out:
                        optimized[company] = out
                    else:
                        # Python fallback: reorder bullets by keyword overlap
                        kws = [s.lower() for s in matched_skills]
                        def _score(b): return sum(1 for k in kws if k in b.lower())
                        sorted_bullets = sorted(bullets, key=_score, reverse=True)
                        optimized[company] = '\n'.join(sorted_bullets)
                if optimized:
                    jd['exp_optimized'] = optimized
                    changed = True
            except Exception as e:
                print(f'  [WARN] exp_optimized failed for {job_folder}: {e}', file=sys.stderr)
        else:
            print(f'  [WARN] cv_parsed not found: cv_parsed_{group_id}.json', file=sys.stderr)

    # ── 2. default_answers ───────────────────────────────────────────────────
    if not jd.get('default_answers'):
        company   = jd.get('company', '')
        title     = jd.get('title', '')
        culture   = ', '.join((jd.get('culture_keywords') or [])[:5])
        matched   = ', '.join((jd.get('matched_skills') or [])[:8])
        core_resp = '\n'.join(f'- {r}' for r in (jd.get('core_responsibilities') or [])[:3])
        # Build CV context
        cv_path2 = user_dir / 'output' / f'cv_parsed_{group_id}.json'
        cv_exp_str = ''
        if cv_path2.exists():
            try:
                cv2 = json.loads(cv_path2.read_text(encoding='utf-8-sig'))
                for exp in cv2.get('experience', [])[:3]:
                    co = exp.get('company','')
                    ttl = exp.get('title','')
                    yr  = exp.get('duration','')
                    cv_exp_str += f'\n- {co} | {ttl} | {yr}'
            except Exception:
                pass
        questions = [
            f'Why do you want to work at {company}?',
            'What is your greatest professional strength?',
            'Walk me through your most relevant project or achievement.',
            f'How does your background prepare you for the {title} role?',
            'Where do you see yourself in the next 3-5 years?',
        ]
        q_block = '\n'.join(f'Q{i+1}: {q}' for i, q in enumerate(questions))
        system_ans = (
            'You are a JSON API. Return ONLY valid JSON — no markdown, no explanation, no code fences. '
            'The JSON must be a single object: {"default_answers":[{"question":"...","answer":"..."},...]} '
            'with exactly 5 items. Each answer ≤120 words, English, citing real companies from the experience list.'
        )
        user_ans = (
            f'Generate 5 interview answers for: {title} at {company}.\n'
            f'Culture: {culture}\nRequired skills: {matched}\n'
            f'Core responsibilities:\n{core_resp}\n'
            f'Candidate experience (cite these, do not invent):{cv_exp_str}\n\n'
            f'Questions:\n{q_block}'
        )
        out = run_api(system_ans, user_ans)
        answers = []
        if out:
            mj = re.search(r'\{[\s\S]*"default_answers"[\s\S]*\}', out)
            if mj:
                try:
                    data = json.loads(mj.group(0))
                    answers = data.get('default_answers', [])
                except Exception:
                    pass
        # Python template fallback when API unavailable or parsing failed
        if len(answers) < 5:
            cv_path3 = user_dir / 'output' / f'cv_parsed_{group_id}.json'
            cv3 = json.loads(cv_path3.read_text(encoding='utf-8-sig')) if cv_path3.exists() else {}
            answers = _template_default_answers(jd, cv3)
            print(f'  [INFO] default_answers: used template fallback (set ANTHROPIC_API_KEY for LLM quality)', file=sys.stderr)
        jd['default_answers'] = answers[:5]
        changed = True

    if changed:
        jd_path.write_text(json.dumps(jd, ensure_ascii=False, indent=2), encoding='utf-8')
        parts = []
        if 'exp_optimized' in jd:
            parts.append(f'{len(jd["exp_optimized"])} exp(s)')
        if 'default_answers' in jd:
            parts.append(f'{len(jd["default_answers"])} answers')
        return f'OK {job_folder} [{", ".join(parts)}]'
    return f'CACHED {job_folder}'


def main():
    parser = argparse.ArgumentParser(description='Pre-generate AI materials for high-score jobs')
    parser.add_argument('--uid',       default='leon',          help='User ID (default: leon)')
    parser.add_argument('--batch-id',  default=None,            help='Batch ID to filter jobs (optional)')
    parser.add_argument('--min-score', type=int, default=DEFAULT_MIN_SCORE, help='Minimum JD Fit score')
    args = parser.parse_args()

    jobs = find_high_score_jobs(args.uid, args.batch_id, args.min_score)
    if not jobs:
        print(f'No jobs found with score >= {args.min_score}.')
        return

    print(f'Pre-generating materials for {len(jobs)} jobs (score >= {args.min_score}, uid={args.uid})...')

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_job, jf, gid, args.uid): jf
            for jf, gid in jobs
        }
        for future in as_completed(futures):
            print(f'  {future.result()}')

    print('Done.')


if __name__ == '__main__':
    main()
