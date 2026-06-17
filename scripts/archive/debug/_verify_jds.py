import json, pathlib

uid = "leon"
queue = json.loads(pathlib.Path("users/{}/output/temp/_jd_queue_today.json".format(uid)).read_text("utf-8"))

print("Checking JD text for {} jobs:".format(len(queue)))
for i, j in enumerate(queue):
    jid = str(j.get("job_id", ""))
    company = j.get("company", "?")[:25]
    has_full = bool(j.get("description_full", "").strip())
    has_snippet = bool(j.get("description_snippet", "").strip())
    full_len = len(j.get("description_full", ""))
    print("  {}. {} [full={}, len={}, snippet={}]".format(
        i+1, company, has_full, full_len, has_snippet).encode("ascii","replace").decode("ascii"))
