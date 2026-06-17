import subprocess, json, sys, pathlib

result = subprocess.run(
    [sys.executable, "scripts/search_state.py", "--mode", "dedup", "--batch-id", "20260614_004", "--uid", "leon"],
    capture_output=True, text=True, encoding="utf-8"
)

print("STDOUT[:200]:", result.stdout[:200])
print("STDERR[:200]:", result.stderr[:200])
print("returncode:", result.returncode)

if result.returncode != 0:
    sys.exit(1)

data = json.loads(result.stdout)
jobs = data.get("display_jobs", [])
to_analyze = [j for j in jobs if not j.get("skip_analysis")]

print("=== Batch 20260614_004 Dedup Results ===")
print("total_new:", data.get("total_new"))
print("skipped_duplicate:", data.get("skipped_duplicate"))
print("hidden_low_score:", data.get("hidden_low_score"))
print("skipped_analysis:", data.get("skipped_analysis"))
print("display_jobs:", len(jobs))
print("to_analyze (skip_analysis=False):", len(to_analyze))
print()
print("Jobs to analyze:")
for i, j in enumerate(to_analyze):
    print("  {}. [score={}] {} | {}".format(
        i+1, j.get("match_score_preview"),
        j.get("company", "")[:35], j.get("title", "")[:55]))

# Save display_jobs for JD analysis
out = pathlib.Path("users/leon/output/temp/_dedup_004_display.json")
out.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nSaved {} display_jobs to {}".format(len(jobs), out))
