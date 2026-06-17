import json, sys, io
sys.path.insert(0, 'scripts')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
from search_state import load_cv_skills, quick_score

skills = load_cv_skills('users/leon/output/cv_parsed_group-pdm.json')
print(f'Skills loaded: {len(skills)}')
print('First 5:', skills[:5] if skills else 'EMPTY')

jobs = json.loads(Path('users/leon/output/temp/_phase2_temp_stepstone.json').read_text(encoding='utf-8'))
j = jobs[1]
score = quick_score(j, skills)
print(f'\nScore for "{j["title"][:40]}": {score}')
print('Snippet preview:', (j.get("description_snippet") or "")[:120])
