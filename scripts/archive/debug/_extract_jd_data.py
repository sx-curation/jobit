import json, sys, io, re, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

uid = sys.argv[1] if len(sys.argv) > 1 else "leon"
batch_id = sys.argv[2] if len(sys.argv) > 2 else "20260607_001"

with open(f"users/{uid}/output/temp/raw_results_{batch_id}.json", encoding="utf-8") as f:
    raw = json.load(f)

with open(f"users/{uid}/output/search_history.json", encoding="utf-8") as f:
    h = json.load(f)
batch = [b for b in h["batches"] if b["batch_id"] == batch_id][0]
job_ids = list(batch.get("job_ids", []))

jobs_list = raw if isinstance(raw, list) else raw.get("jobs", [])
jobs_by_id = {j["job_id"]: j for j in jobs_list}

def slugify(s, max_len=40):
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s.strip())
    return s[:max_len]

batch_date = batch_id[:8]

result = []
for jid in job_ids:
    j = jobs_by_id.get(jid, {})
    company = j.get("company", "")
    title = j.get("title", "")
    company_slug = slugify(company)
    title_slug = slugify(title)
    folder = f"users/{uid}/output/group-pdm_{company_slug}_{title_slug}_{batch_date}"
    result.append({
        "job_id": jid,
        "title": title,
        "company": company,
        "location": j.get("location", ""),
        "url": j.get("url", ""),
        "description_full": j.get("description_full", j.get("description_snippet", "")),
        "_source": j.get("_source", "stepstone"),
        "_group_id": "group-pdm",
        "output_folder": folder
    })

os.makedirs(f"users/{uid}/output/temp", exist_ok=True)
out_path = f"users/{uid}/output/temp/_jd_data_{batch_id}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"Extracted {len(result)} JDs to {out_path}")
