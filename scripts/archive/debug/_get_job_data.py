import json, pathlib, re, sys

uid = "leon"
batch_date = "20260614"
idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0

queue = json.loads(pathlib.Path("users/{}/output/temp/_jd_queue_today.json".format(uid)).read_text("utf-8"))
seen = json.loads(pathlib.Path("users/{}/output/search_history.json".format(uid)).read_text("utf-8")).get("seen_jobs", {})

j = queue[idx]
jid = str(j.get("job_id", ""))
score = seen.get(jid, {}).get("match_score_preview", j.get("match_score_preview", 0))

def slugify(s, max_len=40):
    s = re.sub(r"[^\w\s-]", "", s or "").strip()
    s = re.sub(r"[\s_]+", "-", s)
    return s[:max_len]

company_slug = slugify(j.get("company", ""))
title_slug = slugify(j.get("title", ""))
gid = j.get("_group_id", "group-da")
folder_name = "{}_{}_{}_{}".format(gid, company_slug, title_slug, batch_date)

out = {
    "job_id": jid,
    "title": j.get("title", ""),
    "company": j.get("company", ""),
    "location": j.get("location", ""),
    "url": j.get("url", ""),
    "_source": j.get("_source", "linkedin"),
    "_group_id": gid,
    "match_score_preview": score,
    "output_folder": "users/{}/output/{}".format(uid, folder_name),
    "description_full": j.get("description_full", ""),
}

print(json.dumps(out, ensure_ascii=False))
