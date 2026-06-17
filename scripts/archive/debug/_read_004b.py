import json, pathlib

h = pathlib.Path("users/leon/output/search_history.json")
data = json.loads(h.read_text("utf-8"))

# Collect all new jobs from batch 003 and 004
all_display_job_ids = []
for b in data["batches"]:
    if b["batch_id"] in ("20260614_003", "20260614_004"):
        job_ids = b.get("job_ids", [])
        new_total = b.get("new_total", b.get("total_new"))
        displayed = b.get("displayed")
        dup = b.get("skipped_duplicate")
        hidden = b.get("hidden_low_score")
        skip_a = b.get("skipped_analysis")
        print("=== Batch {} ===".format(b["batch_id"]))
        print("  new_total={}, displayed={}, dup={}, hidden={}, skip_a={}, job_ids={}".format(
            new_total, displayed, dup, hidden, skip_a, len(job_ids)))
        all_display_job_ids.extend(job_ids)

print("\nTotal display job_ids (both batches):", len(all_display_job_ids))

# Load raw 003 and 004 to get full job data
raw003 = json.loads(pathlib.Path("users/leon/output/temp/raw_results_20260614_003.json").read_text("utf-8"))
raw004 = json.loads(pathlib.Path("users/leon/output/temp/raw_results_20260614_004.json").read_text("utf-8"))

# Build job_id -> job map
job_map = {}
for j in raw003:
    job_map[str(j.get("job_id", ""))] = j
for j in raw004:
    job_map[str(j.get("job_id", ""))] = j

# Match and get full data
display_jobs = []
for jid in all_display_job_ids:
    if jid in job_map:
        display_jobs.append(job_map[jid])

print("display_jobs with full data:", len(display_jobs))

# Score preview from seen_jobs
seen = data.get("seen_jobs", {})
print()
to_analyze = []
for i, j in enumerate(display_jobs):
    jid = str(j.get("job_id", ""))
    score = seen.get(jid, {}).get("match_score_preview", j.get("match_score_preview", 0))
    skip = score < 20
    if not skip:
        to_analyze.append(j)
    mark = " [SKIP]" if skip else ""
    print("  {}. [score={:2d}]{} {} | {}".format(
        i+1, score, mark,
        j.get("company", "")[:35], j.get("title", "")[:55]))

print("\nTo analyze (score>=20):", len(to_analyze))

# Save for JD analysis
out = pathlib.Path("users/leon/output/temp/_display_jobs_today.json")
out.write_text(json.dumps(display_jobs, ensure_ascii=False, indent=2), encoding="utf-8")
print("Saved to:", out)
