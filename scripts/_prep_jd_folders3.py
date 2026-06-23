#!/usr/bin/env python3
"""Prepare JD text files from raw_results for display jobs in a batch."""
import json, re
from pathlib import Path

def slugify(text, max_len=40):
    text = re.sub(r'[^\w\s-]', ' ', text)
    text = re.sub(r'\s+', '-', text.strip())
    text = re.sub(r'-+', '-', text)
    return text[:max_len].rstrip('-')

batch_id = '20260619_003'
batch_date = '20260619'
uid = 'leon'
group_id = 'group-pmo'
project_dir = Path(__file__).resolve().parent.parent
output_dir = project_dir / 'users' / uid / 'output'

# Read display job IDs from search_history
hist = json.loads((project_dir / 'users' / uid / 'output' / 'search_history.json').read_text(encoding='utf-8'))
batch = next((b for b in hist['batches'] if b['batch_id'] == batch_id), None)
display_ids = set(str(x) for x in batch.get('job_ids', []))

# Read raw results
raw_path = output_dir / 'temp' / f'raw_results_{batch_id}.json'
raw = json.loads(raw_path.read_text(encoding='utf-8'))
jobs = raw if isinstance(raw, list) else raw.get('jobs', [])

job_map = {str(j.get('job_id', '')): j for j in jobs}

created = []
for job_id in display_ids:
    job = job_map.get(job_id)
    if not job:
        print(f'WARNING: job_id {job_id} not found in raw_results!')
        continue

    company = slugify(job.get('company', 'Unknown'))
    title = slugify(job.get('title', 'Unknown'))
    folder_name = f'{group_id}_{company}_{title}_{batch_date}'
    job_dir = output_dir / folder_name
    job_dir.mkdir(parents=True, exist_ok=True)

    jd_text = job.get('description_full') or job.get('description_snippet', '') or job.get('description', '')
    url = job.get('url', '')
    full_text = f"Title: {job.get('title','')}\nCompany: {job.get('company','')}\nLocation: {job.get('location','')}\nURL: {url}\n\n{jd_text}"
    (job_dir / 'jd_text.txt').write_text(full_text, encoding='utf-8')

    created.append({
        'folder': folder_name,
        'job_id': job_id,
        'title': job.get('title'),
        'company': job.get('company'),
        'score': job.get('match_score_preview', 0),
        'source': job.get('_source', 'linkedin'),
        'group_id': group_id,
    })
    print(f'  {folder_name}  (score={job.get("match_score_preview",0)})')

manifest_path = output_dir / 'temp' / f'_jd_manifest_{batch_id}.json'
manifest_path.write_text(json.dumps(created, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\nManifest: {manifest_path}')
print(f'Total: {len(created)} jobs ready for analysis')
