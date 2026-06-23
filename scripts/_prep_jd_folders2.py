#!/usr/bin/env python3
"""Prepare JD text files for analysis using dedup display_jobs output."""
import json, re, subprocess, sys
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

# Run dedup again to get the display_jobs
result = subprocess.run(
    [sys.executable, 'scripts/search_state.py', '--mode', 'dedup',
     '--batch-id', batch_id, '--uid', uid],
    capture_output=True, text=True, encoding='utf-8',
    cwd=str(project_dir)
)
if result.returncode != 0:
    print('ERROR:', result.stderr)
    sys.exit(1)

data = json.loads(result.stdout)
display_jobs = data.get('display_jobs', [])
print(f'display_jobs: {len(display_jobs)}')
print(f'total_new: {data.get("total_new")}')

# Filter jobs to analyze
jobs_to_analyze = [j for j in display_jobs if not j.get('skip_analysis', False)]
print(f'Jobs to analyze: {len(jobs_to_analyze)}')

# Create folders and write jd_text.txt
created = []
for job in jobs_to_analyze:
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
        'job_id': str(job.get('job_id')),
        'title': job.get('title'),
        'company': job.get('company'),
        'score': job.get('match_score_preview'),
        'source': job.get('_source', 'linkedin'),
        'group_id': group_id,
    })
    print(f'  Created: {folder_name}  (score={job.get("match_score_preview")})')

# Save manifest
manifest_path = output_dir / 'temp' / f'_jd_manifest_{batch_id}.json'
manifest_path.write_text(json.dumps(created, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\nManifest saved: {manifest_path}')
print(json.dumps(created, ensure_ascii=False, indent=2))
