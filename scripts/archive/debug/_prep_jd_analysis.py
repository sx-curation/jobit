"""Print full job data for the 10 display_jobs to analyze."""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

data = json.loads(Path('C:/Users/Admin/.claude/projects/D--JobIt/78b43cfc-9185-4ead-a83d-3017080c146e/tool-results/b0ovx2poh.txt').read_text(encoding='utf-8'))
jobs = data['display_jobs']

for i, j in enumerate(jobs):
    print(f"\n=== JOB {i+1} ===")
    print(f"job_id: {j.get('job_id')}")
    print(f"title: {j.get('title')}")
    print(f"company: {j.get('company')}")
    print(f"location: {j.get('location')}")
    print(f"url: {j.get('url')}")
    print(f"posted_at: {j.get('posted_at')}")
    print(f"source: {j.get('_source')}")
    print(f"score: {j.get('match_score_preview')}")
    print(f"cv_file: {j.get('cv_file')}")
    print(f"cv_parsed: {j.get('cv_parsed')}")
    snippet = j.get('description_snippet','')
    full = j.get('description_full','')
    desc = full if len(full) > len(snippet) else snippet
    print(f"desc_len: {len(desc)}")
