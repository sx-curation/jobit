import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, 'scripts')
import search_state
search_state.init_paths('leon')

config = json.loads((Path('users/leon') / 'config.json').read_text(encoding='utf-8'))
group_meta = search_state.build_group_meta(config)
cv_skills = search_state.load_cv_skills(group_meta['group-pdm']['cv_parsed'])

raw = json.loads(Path('users/leon/output/temp/raw_results_20260610_001.json').read_text(encoding='utf-8'))
h = search_state.load_history()
batch_jobs = {jid for jid, v in h['seen_jobs'].items() if v.get('batch_id') == '20260610_001'}

# Score all batch jobs
from collections import Counter
score_dist = Counter()
sources = Counter()
for j in raw:
    jid = str(j.get('job_id') or j.get('id') or '')
    if jid not in batch_jobs:
        continue
    score = search_state.quick_score(j, cv_skills)
    score_dist[score] += 1
    sources[j.get('_source','?')] += 1

print(f"93 new batch jobs - score distribution:")
for s in sorted(score_dist.keys(), reverse=True)[:20]:
    bar = '#' * score_dist[s]
    print(f"  {s:>3}: {bar} ({score_dist[s]})")

print(f"\nSources: {dict(sources)}")
print(f"\nJobs with score >= 20: {sum(v for k,v in score_dist.items() if k >= 20)}")
print(f"Jobs with score < 20: {sum(v for k,v in score_dist.items() if k < 20)}")
print(f"Jobs with score == 0: {score_dist.get(0,0)}")
