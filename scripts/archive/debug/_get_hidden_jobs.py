"""Get all new jobs from batch with score >= 20 that haven't been analyzed yet."""
import json, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

sys.path.insert(0, 'scripts')
import search_state
search_state.init_paths('leon')

# Load config for scoring
config = json.loads((Path('users/leon') / 'config.json').read_text(encoding='utf-8'))
group_meta = search_state.build_group_meta(config)
cv_skills = search_state.load_cv_skills(group_meta['group-pdm']['cv_parsed'])
min_score = config['job_search'].get('min_score_for_analysis', 20)

# Load raw results
raw = json.loads((Path('users/leon/output/temp/raw_results_20260610_001.json')).read_text(encoding='utf-8'))

# Load history to find which are new (batch 20260610_001)
h = search_state.load_history()
seen = h['seen_jobs']
batch_jobs = {jid for jid, v in seen.items() if v.get('batch_id') == '20260610_001'}

print(f"Total raw: {len(raw)}, In batch (new): {len(batch_jobs)}")

def slugify(s, max_len=40):
    s = re.sub(r'[^\w\s-]', '', str(s))
    s = re.sub(r'[\s_]+', '-', s.strip())
    return s[:max_len]

# Score and filter
qualifying = []
for j in raw:
    jid = str(j.get('job_id') or j.get('id') or '')
    if jid not in batch_jobs:
        continue
    gid = j.get('_group_id', '')
    if gid != 'group-pdm':
        continue
    score = search_state.quick_score(j, cv_skills)
    if score < min_score:
        continue

    co_slug = slugify(j.get('company', ''))
    ti_slug = slugify(j.get('title', ''))
    folder = f"group-pdm_{co_slug}_{ti_slug}_20260610"
    jd_path = Path('users/leon/output') / folder / 'jd_analysis.json'

    if jd_path.exists():
        continue  # already analyzed

    snip = j.get('description_snippet', '') or ''
    full = j.get('description_full', '') or ''
    desc = full if len(full) >= len(snip) else snip

    qualifying.append({
        'job_id': jid,
        'title': j.get('title', ''),
        'company': j.get('company', ''),
        'location': j.get('location', ''),
        'url': j.get('url', ''),
        'posted_at': j.get('posted_at'),
        'source': j.get('_source', 'stepstone'),
        'score': score,
        'folder': folder,
        'out_dir': str(Path('users/leon/output') / folder),
        'desc_len': len(desc),
        'desc': desc,
    })

qualifying.sort(key=lambda x: x['score'], reverse=True)
print(f"Qualifying (score>={min_score}, not yet analyzed): {len(qualifying)}")
print(f"Score distribution:")
from collections import Counter
score_dist = Counter(j['score'] for j in qualifying)
for s in sorted(score_dist.keys(), reverse=True):
    print(f"  score={s}: {score_dist[s]} jobs")

# Create dirs and save
for j in qualifying:
    Path(j['out_dir']).mkdir(parents=True, exist_ok=True)

out = Path('scripts/_hidden_jobs.json')
out.write_text(json.dumps(qualifying, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"\nSaved to {out}")
