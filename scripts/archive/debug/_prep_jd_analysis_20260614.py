import json, pathlib, re

uid = "leon"
batch_date = "20260614"

# Load batch 003 and 004 display jobs
jobs003 = json.loads(pathlib.Path("users/{}/output/temp/_display_jobs_003.json".format(uid)).read_text("utf-8"))
jobs004 = json.loads(pathlib.Path("users/{}/output/temp/_display_jobs_today.json".format(uid)).read_text("utf-8"))

all_jobs = jobs003 + jobs004
print("Total display jobs:", len(all_jobs))

# Deduplicate by job_id
seen_ids = set()
unique_jobs = []
for j in all_jobs:
    jid = str(j.get("job_id", ""))
    if jid not in seen_ids:
        seen_ids.add(jid)
        unique_jobs.append(j)

print("Unique jobs:", len(unique_jobs))

def slugify(s, max_len=40):
    s = re.sub(r"[^\w\s-]", "", s or "").strip()
    s = re.sub(r"[\s_]+", "-", s)
    return s[:max_len]

output_base = pathlib.Path("users/{}/output".format(uid))

jobs_needing_analysis = []
for j in unique_jobs:
    gid = j.get("_group_id", "group-da")
    company = j.get("company", "")
    title = j.get("title", "")
    jid = str(j.get("job_id", ""))
    score = j.get("match_score_preview", 0)

    company_slug = slugify(company)
    title_slug = slugify(title)
    folder_name = "{}_{}_{}_{}/".format(gid, company_slug, title_slug, batch_date)

    # Check if output folder exists and has jd_analysis.json
    folder = output_base / "{}_{}_{}_{}".format(gid, company_slug, title_slug, batch_date)
    has_analysis = (folder / "jd_analysis.json").exists()

    status = "DONE" if has_analysis else "PENDING"
    line = "  [{}] [score={:2d}] {} | {} -> {}".format(
        status, score, company[:30], title[:45], folder.name[:50])
    print(line.encode("ascii", "replace").decode("ascii"))

    if not has_analysis:
        j["_output_folder"] = str(folder)
        j["_batch_date"] = batch_date
        jobs_needing_analysis.append(j)

print("\nJobs needing JD analysis:", len(jobs_needing_analysis))

# Save
out = pathlib.Path("users/{}/output/temp/_jd_queue_today.json".format(uid))
out.write_text(json.dumps(jobs_needing_analysis, ensure_ascii=False, indent=2), encoding="utf-8")
print("Saved queue to:", out)
