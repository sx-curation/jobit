import subprocess, json, sys, pathlib

result = subprocess.run(
    [sys.executable, "scripts/search_state.py", "--mode", "dedup", "--batch-id", "20260614_003", "--uid", "leon", "--force"],
    capture_output=True, text=True, encoding="utf-8"
)

data = json.loads(result.stdout)
jobs = data.get("display_jobs", [])
print("display_jobs:", len(jobs))
print("total_new:", data.get("total_new"))
print("skipped_duplicate:", data.get("skipped_duplicate"))
print("hidden_low_score:", data.get("hidden_low_score"))
print("skipped_analysis:", data.get("skipped_analysis"))
print()
for i, j in enumerate(jobs):
    print("  {}. [score={}] [skip_analysis={}] {} | {}".format(
        i+1, j.get("match_score_preview"), j.get("skip_analysis"),
        j.get("company", "")[:35], j.get("title", "")[:55]))

# Save for later use
out = pathlib.Path("users/leon/output/temp/_dedup_003_display.json")
out.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nSaved to:", out)
