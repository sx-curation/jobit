"""Output full JD text and metadata for each display_job as JSON."""
import json, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

data = json.loads(Path('C:/Users/Admin/.claude/projects/D--JobIt/78b43cfc-9185-4ead-a83d-3017080c146e/tool-results/b0ovx2poh.txt').read_text(encoding='utf-8'))

def slugify(s, max_len=40):
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s.strip())
    return s[:max_len]

jobs_out = []
for j in data['display_jobs']:
    snip = j.get('description_snippet','') or ''
    full = j.get('description_full','') or ''
    desc = full if len(full) >= len(snip) else snip
    co_slug = slugify(j.get('company',''))
    ti_slug = slugify(j.get('title',''))
    folder = f"group-pdm_{co_slug}_{ti_slug}_20260610"
    jobs_out.append({
        'job_id': j.get('job_id'),
        'title': j.get('title'),
        'company': j.get('company'),
        'location': j.get('location'),
        'url': j.get('url'),
        'posted_at': j.get('posted_at'),
        'source': j.get('_source','stepstone'),
        'score': j.get('match_score_preview'),
        'folder': folder,
        'desc': desc,
    })

print(json.dumps(jobs_out, ensure_ascii=False, indent=2))
