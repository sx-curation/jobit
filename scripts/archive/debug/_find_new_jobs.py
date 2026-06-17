import json, pathlib, sys

h = pathlib.Path("users/leon/output/search_history.json")
data = json.loads(h.read_text("utf-8"))
seen = data.get("seen_jobs", {})

sample = list(seen.items())[:2]
print("seen_jobs type:", type(list(seen.values())[0]))
print("sample key:", list(seen.keys())[0])
print("sample value:", list(seen.values())[0])

# Find jobs first seen in batch 003
batch003_jobs = []
for job_id, batch_info in seen.items():
    if isinstance(batch_info, dict):
        if batch_info.get("batch_id") == "20260614_003":
            batch003_jobs.append(job_id)
    elif isinstance(batch_info, str):
        if batch_info == "20260614_003":
            batch003_jobs.append(job_id)

print("\nJobs from batch 003:", len(batch003_jobs))
print("First 5:", batch003_jobs[:5])
