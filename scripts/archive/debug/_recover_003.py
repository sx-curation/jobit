import json, pathlib, re

# Recover batch 003 display jobs from seen_jobs + raw data
h = pathlib.Path("users/leon/output/search_history.json")
data = json.loads(h.read_text("utf-8"))
seen = data.get("seen_jobs", {})

# 29 job IDs first seen in batch 003
batch003_ids = [k for k, v in seen.items() if isinstance(v, dict) and v.get("batch_id") == "20260614_003"]
print("Batch 003 job IDs:", len(batch003_ids))

# Load raw 003 to get full data
raw003 = json.loads(pathlib.Path("users/leon/output/temp/raw_results_20260614_003.json").read_text("utf-8"))
job_map = {str(j.get("job_id", "")): j for j in raw003}

# Load cv skills for scoring
cv_parsed = json.loads(pathlib.Path("users/leon/output/cv_parsed_group-da.json").read_text("utf-8"))
skills = []
for exp in cv_parsed.get("experience", []):
    skills.extend(exp.get("skills", []))
cv_skills = cv_parsed.get("skills", [])
if isinstance(cv_skills, dict):
    for s in cv_skills.values():
        if isinstance(s, list):
            skills.extend(s)
elif isinstance(cv_skills, list):
    skills.extend(cv_skills)
skills = [s.lower() for s in skills if isinstance(s, str)]

# Load skill taxonomy
config = json.loads(pathlib.Path("users/leon/config.json").read_text("utf-8"))
tool_list = [t.lower() for t in config.get("skill_taxonomy", {}).get("tools", [])]

def quick_score(job, skills_lower):
    text = " ".join([
        job.get("title", ""), job.get("description_full", ""), job.get("description_snippet", "")
    ]).lower()
    hits = sum(1 for s in tool_list if s in text)
    cv_hits = sum(1 for s in skills_lower if s and s in text)
    return min(100, hits * 3 + cv_hits * 2)

# Build display list
batch003_jobs = []
for jid in batch003_ids:
    if jid in job_map:
        j = job_map[jid]
        score = seen.get(jid, {}).get("match_score_preview", quick_score(j, skills))
        j["match_score_preview"] = score
        j["skip_analysis"] = score < 20
        batch003_jobs.append(j)

batch003_jobs.sort(key=lambda j: j["match_score_preview"], reverse=True)

# Show top 10 (display_jobs)
min_score_display = 20
display003 = [j for j in batch003_jobs if not j.get("skip_analysis")][:10]

print("Batch 003 display jobs (score>=20):", len(display003))
for i, j in enumerate(display003):
    line = "  {}. [score={:2d}] {} | {}".format(
        i+1, j.get("match_score_preview", 0),
        j.get("company", "")[:35], j.get("title", "")[:55])
    print(line.encode("ascii", "replace").decode("ascii"))

# Save
out = pathlib.Path("users/leon/output/temp/_display_jobs_003.json")
out.write_text(json.dumps(display003, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nSaved to:", out)
