import json, sys, io, re, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

uid = sys.argv[1] if len(sys.argv) > 1 else "leon"
batch_id = sys.argv[2] if len(sys.argv) > 2 else "20260607_001"

target_ids = [
    "st_592bda0e8ec88e72",
    "st_27630d0fa1b676c6",
    "st_9b40ff62529967b1",
    "st_ba30da358bff5903",
    "st_19cf85df306f3f27",
    "st_f8d299f80cb99289",
    "st_daec2f335b2aab7b",
    "st_b331aefdc290593e",
    "st_9fb0bd1b4fee18a3",
]

with open(f"users/{uid}/output/temp/raw_results_{batch_id}.json", encoding="utf-8") as f:
    raw = json.load(f)

jobs_list = raw if isinstance(raw, list) else raw.get("jobs", [])
jobs_by_id = {j["job_id"]: j for j in jobs_list}

def slugify(s, max_len=40):
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s]+", "-", s.strip())
    return s[:max_len]

batch_date = batch_id[:8]
result = []
for jid in target_ids:
    j = jobs_by_id.get(jid, {})
    if not j.get("title"):
        print(f"SKIP {jid} — no title data")
        continue
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
    print(f"OK {jid} | {title[:50]} @ {company[:30]}")
    print(f"   → {folder}")

out_path = f"users/{uid}/output/temp/_jd_data_extra_{batch_id}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"\nSaved {len(result)} jobs to {out_path}")
