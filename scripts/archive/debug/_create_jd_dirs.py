"""Create output directories for each job and print job info for jd-analyzer."""
import json, re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

raw = Path('C:/Users/Admin/.claude/projects/D--JobIt/78b43cfc-9185-4ead-a83d-3017080c146e/tool-results/b0ovx2poh.txt').read_bytes()
# Strip BOM if present
if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
    data = json.loads(raw.decode('utf-16'))
else:
    data = json.loads(raw.decode('utf-8'))

def slugify(s, max_len=40):
    s = re.sub(r'[^\w\s-]', '', str(s))
    s = re.sub(r'[\s_]+', '-', s.strip())
    return s[:max_len]

base_output = Path('users/leon/output')
jobs_info = []

for j in data['display_jobs']:
    co_slug = slugify(j.get('company', ''))
    ti_slug = slugify(j.get('title', ''))
    folder = f"group-pdm_{co_slug}_{ti_slug}_20260610"
    out_dir = base_output / folder
    out_dir.mkdir(parents=True, exist_ok=True)

    snip = j.get('description_snippet', '') or ''
    full = j.get('description_full', '') or ''
    desc = full if len(full) >= len(snip) else snip

    jobs_info.append({
        'job_id': j.get('job_id'),
        'title': j.get('title'),
        'company': j.get('company'),
        'location': j.get('location'),
        'url': j.get('url'),
        'posted_at': j.get('posted_at'),
        'source': j.get('_source', 'stepstone'),
        'score': j.get('match_score_preview'),
        'folder': folder,
        'out_dir': str(out_dir),
        'desc_len': len(desc),
        'desc': desc,
    })
    print(f"Created: {out_dir}")

# Save for reference
out_path = Path('scripts/_jd_jobs.json')
out_path.write_text(json.dumps(jobs_info, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"\nSaved {len(jobs_info)} jobs to {out_path}")
