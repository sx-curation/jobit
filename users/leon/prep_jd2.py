import json, sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
dedup = json.load(open("C:/Users/Admin/.claude/projects/D--JobIt-1-generate-linkedin-cv/dd977f7b-e24a-4009-88b0-9dd0ea8b9e8d/tool-results/bhgndkqsv.txt", encoding="utf-8"))
display_jobs = dedup.get("display_jobs", [])
raw = json.load(open("output/temp/raw_results_20260602_001.json", encoding="utf-8"))
raw_by_id = {str(j.get("job_id","")): j for j in raw}
def slugify(s, maxlen=40):
    s = re.sub(r"[^\w\s-]", "", s or ""); s = re.sub(r"[\s_]+", "-", s).strip("-"); return s[:maxlen]
jobs_out = []
for job in display_jobs:
    jid = str(job.get("job_id",""))
    r = raw_by_id.get(jid, {})
    company = job.get("company","") or r.get("company","")
    title   = job.get("title","")   or r.get("title","")
    out_dir = f"output/group-pdm_{slugify(company)}_{slugify(title)}_20260602"
    full_desc = r.get("description_full") or r.get("description") or r.get("description_snippet") or ""
    jobs_out.append({"job_id":jid,"company":company,"title":title,"location":job.get("location",""),"url":job.get("url","") or r.get("url",""),"pre_score":job.get("match_score_preview",0),"description":full_desc,"output_dir":out_dir,"_source":"linkedin"})
    print(f"  [{job.get('match_score_preview',0):3}] {company[:28]:<28} desc={len(full_desc)}  {out_dir.split('/')[-1]}")
json.dump(jobs_out, open("output/temp/jd_queue.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Saved {len(jobs_out)} jobs to jd_queue.json")