import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

h = json.loads(Path('users/leon/output/search_history.json').read_text(encoding='utf-8'))
seen = h.get('seen_jobs', {})

pdm_jobs = {jid: info for jid, info in seen.items()
            if info.get('group_id') == 'group-pdm'}

scores = sorted(pdm_jobs.values(), key=lambda x: x.get('match_score_preview', 0), reverse=True)

above_threshold = [j for j in scores if j.get('match_score_preview', 0) >= 20]
print(f'group-pdm in history: {len(pdm_jobs)} | score>=20: {len(above_threshold)}')
print('\nTop 10 by score:')
for j in scores[:10]:
    score = j.get('match_score_preview', 0)
    src = j.get('source', '?')
    title = str(j.get('keyword', ''))[:40]
    print(f'  [{score:>3}] [{src:>9}] {title}')
