import json
from pathlib import Path

result_file = Path("users/leon/output/temp/dedup_result.json")
raw = json.loads(result_file.read_bytes())
data = raw.get("display_jobs", raw) if isinstance(raw, dict) else raw

new_jobs = [j for j in data if not j.get("_seen_before", False)]
print("Total display jobs: %d" % len(data))
print("New jobs (not seen before): %d" % len(new_jobs))
print("Skipped duplicates: %d" % (raw.get("skipped_duplicate", 0) if isinstance(raw, dict) else 0))
print()
for j in new_jobs:
    score = j.get("_pre_score", 0)
    company = j["company"][:35]
    title = j["title"][:55]
    print("  score=%-3.0f | %-35s | %s" % (score, company, title))
