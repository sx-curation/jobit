import subprocess, shutil, json, re
from pathlib import Path

def _extract_qa(text):
    try:
        clean = re.sub(r'```(?:json)?\s*|\s*```', '', text)
        m = re.search(r'\{"default_answers"\s*:\s*\[[\s\S]*?\]\s*\}', clean)
        if m:
            parsed = json.loads(m.group())
            if parsed.get('default_answers'):
                return parsed['default_answers']
    except Exception:
        pass
    pairs = []
    parts = re.split(r'(?m)^##\s+Q\d+\s*', text)
    print(f'DEBUG: split produced {len(parts)} parts')
    for i, part in enumerate(parts[1:], 1):
        lines = part.strip().split('\n')
        print(f'  part[{i}] line[0]: {repr(lines[0][:80])}')
        q = re.sub(r'^[^\w]*', '', lines[0]).strip()
        rest = '\n'.join(lines[1:])
        a_match = re.search(r'\*\*A(?:nswer)?:\*\*\s*([\s\S]+)', rest)
        print(f'  q={repr(q[:40])}, a_match={bool(a_match)}')
        if not a_match:
            continue
        a_raw = a_match.group(1).strip()
        a_raw = re.sub(r'\*\*(.*?)\*\*', r'\1', a_raw)
        a_raw = re.sub(r'\*(.*?)\*', r'\1', a_raw)
        a_raw = re.sub(r'^[-—]+$', '', a_raw, flags=re.MULTILINE)
        a_clean = re.sub(r'\s+', ' ', a_raw).strip()
        if q and a_clean:
            pairs.append({'question': q, 'answer': a_clean})
    return pairs[:5]

uid = 'leon'
job_folder = 'group-da_Accel-Club_Senior-Performance-Marketing-Specialist_20260528'
user_dir = Path(__file__).parent.parent / 'users' / uid
jd_file = user_dir / 'output' / job_folder / 'jd_analysis.json'

jd = json.loads(jd_file.read_text(encoding='utf-8'))
company = jd.get('company', '')
title   = jd.get('title', '')
cores   = jd.get('core_responsibilities', [])[:5]
matched = jd.get('matched_skills', [])[:8]
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

claude_bin = shutil.which('claude')
proc = subprocess.run(
    [claude_bin, '-p', prompt],
    cwd=str(user_dir),
    capture_output=True, text=True,
    encoding='utf-8', errors='replace',
    timeout=90,
)
print('returncode:', proc.returncode)
print('--- raw stdout (first 800) ---')
print(repr(proc.stdout[:800]))
print()
answers = _extract_qa(proc.stdout)
print('parsed answers count:', len(answers))
for i, a in enumerate(answers):
    print(f'  Q{i+1}: {a["question"][:70]}')
