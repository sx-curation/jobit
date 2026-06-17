import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

data = json.loads(Path('C:/Users/Admin/.claude/projects/D--JobIt/78b43cfc-9185-4ead-a83d-3017080c146e/tool-results/b0ovx2poh.txt').read_text(encoding='utf-8'))
for j in data['display_jobs']:
    snip = len(j.get('description_snippet','') or '')
    full = len(j.get('description_full','') or '')
    print(f"[{j['match_score_preview']:>2}] {j['title'][:40]:40s} | snippet={snip:>5} full={full:>5}")
