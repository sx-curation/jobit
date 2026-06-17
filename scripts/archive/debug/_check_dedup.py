import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

data = json.loads(Path('users/leon/output/temp/raw_results_20260610_001.json').read_text(encoding='utf-8'))
jobs = data.get('display_jobs', data) if isinstance(data, dict) else data

all_groups = {}
for j in jobs:
    g = j.get('_group_id', '?')
    all_groups[g] = all_groups.get(g, 0) + 1

print('=== 各 group 去重后职缺数 ===')
for g, n in sorted(all_groups.items()):
    print(f'  {g}: {n}')

pdm = [j for j in jobs if j.get('_group_id') == 'group-pdm']
pdm_sorted = sorted(pdm, key=lambda j: j.get('match_score_preview', 0), reverse=True)
print(f'\n=== group-pdm: {len(pdm)} 个职缺（前15，按预评分排序）===')
for j in pdm_sorted[:15]:
    src = j.get('_source', '?')
    score = j.get('match_score_preview', 0)
    title = j.get('title', '')[:45]
    company = j.get('company', '')[:28]
    print(f'  [{score:>3}] [{src:>9}] {title} @ {company}')
