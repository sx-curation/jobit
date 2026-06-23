#!/usr/bin/env python3
"""Prepare JD text files for analysis. Called once per batch."""
import json, re, sys
from pathlib import Path

def slugify(text, max_len=40):
    text = re.sub(r'[^\w\s-]', ' ', text)
    text = re.sub(r'\s+', '-', text.strip())
    text = re.sub(r'-+', '-', text)
    return text[:max_len].rstrip('-')

batch_id = '20260619_002'
batch_date = '20260619'
uid = 'leon'
project_dir = Path(__file__).resolve().parent.parent
output_dir = project_dir / 'users' / uid / 'output'
min_score = 20

# Read raw results
raw_path = output_dir / 'temp' / f'raw_results_{batch_id}.json'
raw = json.loads(raw_path.read_text(encoding='utf-8'))
jobs = raw if isinstance(raw, list) else raw.get('jobs', [])

print(f'Total raw jobs: {len(jobs)}')

# Read search_history for seen_jobs
history_path = output_dir / 'search_history.json'
history = json.loads(history_path.read_text(encoding='utf-8'))

# Get seen_jobs from previous batches (not this batch)
seen_jobs = set()
for b in history['batches']:
    if b['batch_id'] != batch_id:
        seen_jobs.update(b.get('job_ids', []))

print(f'Already seen job_ids (prior batches): {len(seen_jobs)}')

# Deduplicate and filter
current_batch_ids = set()
jobs_to_analyze = []
for job in jobs:
    job_id = str(job.get('job_id', ''))
    if not job_id:
        continue
    if job_id in seen_jobs:
        continue
    if job_id in current_batch_ids:
        continue
    current_batch_ids.add(job_id)
    score = job.get('match_score_preview', 0)
    if score >= min_score:
        jobs_to_analyze.append(job)

print(f'Jobs to analyze (score >= {min_score}): {len(jobs_to_analyze)}')

# Create folders and write jd_text.txt
created = []
for job in sorted(jobs_to_analyze, key=lambda j: j.get('match_score_preview', 0), reverse=True):
    company = slugify(job.get('company', 'Unknown'))
    title = slugify(job.get('title', 'Unknown'))
    group_id = job.get('_group_id', 'group-partner-success')
    folder_name = f'{group_id}_{company}_{title}_{batch_date}'
    job_dir = output_dir / folder_name
    job_dir.mkdir(parents=True, exist_ok=True)

    jd_text = job.get('description_full') or job.get('description_snippet', '')
    (job_dir / 'jd_text.txt').write_text(jd_text, encoding='utf-8')

    created.append({
        'folder': folder_name,
        'job_id': job.get('job_id'),
        'title': job.get('title'),
        'company': job.get('company'),
        'score': job.get('match_score_preview'),
        'source': job.get('_source', 'linkedin'),
    })
    print(f'  Created: {folder_name}  (score={job.get("match_score_preview")})')

# Save manifest
manifest_path = output_dir / 'temp' / f'_jd_manifest_{batch_id}.json'
manifest_path.write_text(json.dumps(created, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\nManifest saved: {manifest_path}')
