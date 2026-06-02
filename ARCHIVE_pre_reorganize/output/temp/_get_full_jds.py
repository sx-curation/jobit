import json, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

raw = json.loads(Path("output/temp/raw_results_20260530_002.json").read_text(encoding="utf-8"))
target_ids = {"4412129900", "4411725603", "4422054840"}
for job in raw:
    jid = str(job.get("job_id", ""))
    if jid in target_ids:
        out = {
            "job_id": jid,
            "title": job.get("title",""),
            "company": job.get("company",""),
            "location": job.get("location",""),
            "url": job.get("url",""),
            "description_full": job.get("description_full","") or job.get("description_snippet",""),
            "_keyword": job.get("_keyword",""),
            "_source": job.get("_source","linkedin"),
            "_group_id": job.get("_group_id","group-pmo"),
        }
        Path(f"output/temp/_jd_{jid}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved: output/temp/_jd_{jid}.json  ({len(out['description_full'])} chars)")
