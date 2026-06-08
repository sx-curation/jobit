import json, sys, io, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

uid = sys.argv[1] if len(sys.argv) > 1 else "leon"
batch_id = sys.argv[2] if len(sys.argv) > 2 else "20260607_001"

with open(f"users/{uid}/output/search_history.json", encoding="utf-8") as f:
    h = json.load(f)

batch = [b for b in h["batches"] if b["batch_id"] == batch_id][0]
seen_jobs = set()
for b in h["batches"]:
    if b["batch_id"] == batch_id:
        continue
    seen_jobs.update(b.get("job_ids", []))

raw_path = f"users/{uid}/output/temp/raw_results_{batch_id}.json"
with open(raw_path, encoding="utf-8") as f:
    raw = json.load(f)

jobs = raw if isinstance(raw, list) else raw.get("jobs", [])
new_jobs = [j for j in jobs if j.get("job_id") not in seen_jobs]

displayed_ids = set(batch.get("job_ids", []))

print(f"總計抓取: {len(jobs)}  新職缺: {len(new_jobs)}  顯示Top10: {len(displayed_ids)}\n")
print(f"{'#':<4} {'Score':<7} {'Status':<8} {'Job ID':<22} {'Title[:45]':<47} {'Company[:25]'}")
print("-" * 120)

new_jobs_sorted = sorted(new_jobs, key=lambda j: j.get("match_score_preview", 0), reverse=True)
for i, j in enumerate(new_jobs_sorted, 1):
    score = j.get("match_score_preview", 0)
    jid = j.get("job_id", "")
    title = j.get("title", "")[:45]
    company = j.get("company", "")[:25]
    status = "✅TOP10" if jid in displayed_ids else "---"
    print(f"{i:<4} {score:<7} {status:<8} {jid:<22} {title:<47} {company}")
