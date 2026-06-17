import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

data = json.loads(Path('C:/Users/Admin/.claude/projects/D--JobIt/78b43cfc-9185-4ead-a83d-3017080c146e/tool-results/b0ovx2poh.txt').read_text(encoding='utf-8'))

jobs = data.get('display_jobs', [])
total_new = data.get('total_new', 0)
skipped = data.get('skipped_duplicate', 0)
hidden = data.get('hidden_low_score', 0)
skip_analysis = data.get('skipped_analysis', 0)

print(f"total_new={total_new} | displayed={len(jobs)} | skipped_dup={skipped} | hidden_low={hidden} | skip_analysis={skip_analysis}")

by_group = {}
for j in jobs:
    g = j.get('_group_id', '?')
    by_group.setdefault(g, []).append(j)

for g, gjobs in sorted(by_group.items()):
    to_analyze = [j for j in gjobs if not j.get('skip_analysis')]
    print(f"\n{g}: {len(gjobs)} jobs | to_analyze={len(to_analyze)}")
    for j in sorted(gjobs, key=lambda x: x.get('match_score_preview',0), reverse=True)[:10]:
        src = j.get('_source','?')
        score = j.get('match_score_preview', 0)
        skip = 'SKIP' if j.get('skip_analysis') else 'ANALYZE'
        title = j.get('title','')[:42]
        company = j.get('company','')[:25]
        print(f"  [{score:>3}] [{src:>9}] [{skip}] {title} @ {company}")
