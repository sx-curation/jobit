import json, sys
uid = sys.argv[1] if len(sys.argv) > 1 else "leon"
batch_id = sys.argv[2] if len(sys.argv) > 2 else "20260607_001"
with open(f"users/{uid}/output/search_history.json", encoding="utf-8") as f:
    h = json.load(f)
batch = [b for b in h["batches"] if b["batch_id"] == batch_id][0]
jobs = batch.get("display_jobs", [])
print(f"Total display_jobs: {len(jobs)}")
for i, j in enumerate(jobs):
    score = j.get("match_score_preview", 0)
    title = j.get("title", "")[:55]
    company = j.get("company", "")[:28]
    jid = j.get("job_id", "")
    url = j.get("url", "")
    print(f"{i+1}. [{score}] {jid} | {title} @ {company}")
