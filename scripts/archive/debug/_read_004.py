import json, pathlib

h = pathlib.Path("users/leon/output/search_history.json")
data = json.loads(h.read_text("utf-8"))

for b in data["batches"]:
    if b["batch_id"] == "20260614_004":
        jobs = b.get("display_jobs", [])
        total_new = b.get("total_new")
        dup = b.get("skipped_duplicate")
        hidden = b.get("hidden_low_score")
        skip_a = b.get("skipped_analysis")
        to_analyze = [j for j in jobs if not j.get("skip_analysis")]

        print("=== Batch 20260614_004 ===")
        print("total_new:", total_new)
        print("skipped_duplicate:", dup)
        print("hidden_low_score:", hidden)
        print("skipped_analysis:", skip_a)
        print("display_jobs:", len(jobs))
        print("to_analyze:", len(to_analyze))
        print()

        for i, j in enumerate(jobs):
            mark = " [SKIP]" if j.get("skip_analysis") else ""
            print("  {}. [score={:2d}]{} {} | {}".format(
                i+1, j.get("match_score_preview", 0), mark,
                j.get("company", "")[:35], j.get("title", "")[:55]))

        # Save for JD analysis
        out = pathlib.Path("users/leon/output/temp/_dedup_004_display.json")
        out.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\nSaved {} display_jobs to {}".format(len(jobs), out))
        break
