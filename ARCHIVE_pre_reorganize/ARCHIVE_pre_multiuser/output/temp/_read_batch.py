import json, sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

h = json.loads(Path("output/search_history.json").read_text(encoding="utf-8"))
seen = h["seen_jobs"]

batch_jobs = [(jid, j) for jid, j in seen.items() if j.get("batch_id") == "20260530_002"]
batch_jobs.sort(key=lambda x: x[1].get("match_score_preview", 0), reverse=True)

scores = [j.get("match_score_preview", 0) for _, j in batch_jobs]
print(f"Total in batch: {len(batch_jobs)}")
print(f"score>=50: {sum(1 for s in scores if s >= 50)}")
print(f"score>=30: {sum(1 for s in scores if s >= 30)}")
print(f"score>=20: {sum(1 for s in scores if s >= 20)}")
print()

PRIMARY_KWS = {"PMO Manager","Project Management Officer","Strategic PMO Lead",
               "Business Transformation Manager","Chief of Staff","Projektmanagement-Experte",
               "Leiter Projektmanagementoffice","Change Manager","Transformation Manager"}

print("Top 10 by score:")
for i, (jid, j) in enumerate(batch_jobs[:10], 1):
    t = j.get("title", "")[:52]
    c = j.get("company", "")[:28]
    kw = j.get("keyword", "")[:35]
    kt = "primary" if kw.strip() in PRIMARY_KWS else "fallback"
    print(f"{i:2}. [{j.get('match_score_preview',0):3}] [{kt:<8}]  {t:<54} @ {c}")
    print(f"        kw: {kw}  |  {j.get('source','')}")
