import json, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

raw = json.loads(Path("output/temp/raw_results_20260530_002.json").read_text(encoding="utf-8"))
target_ids = {"4412129900", "4411725603", "4422054840"}
found = {}
for job in raw:
    jid = str(job.get("job_id", ""))
    if jid in target_ids:
        found[jid] = job

for jid in ["4412129900", "4411725603", "4422054840"]:
    job = found.get(jid, {})
    print(f"=== JOB {jid} ===")
    print(f"Title:    {job.get('title','')}")
    print(f"Company:  {job.get('company','')}")
    print(f"Location: {job.get('location','')}")
    print(f"URL:      {job.get('url','')}")
    print(f"Keyword:  {job.get('_keyword','')}  |  Source: {job.get('_source','')}")
    desc = job.get("description_full", "") or job.get("description_snippet", "")
    print(f"Desc len: {len(desc)}")
    print(desc[:300])
    print()
