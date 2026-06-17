import json, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

uid = sys.argv[1] if len(sys.argv) > 1 else "leon"
batch_id = sys.argv[2] if len(sys.argv) > 2 else "20260607_001"

with open(f"users/{uid}/output/temp/raw_results_{batch_id}.json", encoding="utf-8") as f:
    raw = json.load(f)

with open(f"users/{uid}/output/search_history.json", encoding="utf-8") as f:
    h = json.load(f)
batch = [b for b in h["batches"] if b["batch_id"] == batch_id][0]
job_ids = set(batch.get("job_ids", []))

jobs_list = raw if isinstance(raw, list) else raw.get("jobs", [])
display = [j for j in jobs_list if j.get("job_id") in job_ids]

print(f"Display jobs: {len(display)}")
for i, j in enumerate(display):
    score = j.get("match_score_preview", 0)
    title = j.get("title", "")[:55]
    company = j.get("company", "")[:28]
    jid = j.get("job_id", "")
    print(f"{i+1}. [{score}] {jid} | {title} @ {company}")
