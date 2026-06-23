import json, pathlib

raw_path = pathlib.Path('users/leon/output/temp/raw_results_20260619_003.json')
raw = json.load(open(raw_path, encoding='utf-8'))
target_ids = ['4428257003','4430449276','4429677997','4429329592','4427851199',
              '4429792292','4430422058','4402923895','4418273575','4430968850']

jobs_list = raw if isinstance(raw, list) else raw.get('jobs', [])
jobs_map = {}
for job in jobs_list:
    jid = str(job.get('job_id', ''))
    if jid in target_ids:
        jobs_map[jid] = job

print('Found:', len(jobs_map))
for jid in target_ids:
    job = jobs_map.get(jid)
    if job:
        title = job.get('title', '?')[:50]
        co = job.get('company', '?')[:30]
        score = job.get('match_score_preview', 0)
        group = job.get('_group_id', job.get('group_id', '?'))
        print(f'  {jid}: {title} @ {co} | score={score} | group={group}')
    else:
        print(f'  {jid}: NOT FOUND')
