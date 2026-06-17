import json, pathlib, sys

uid = "leon"
li_path = pathlib.Path("users/{}/output/temp/_phase2_temp.json".format(uid))
merged_path = pathlib.Path("users/{}/output/temp/_phase2_temp_merged.json".format(uid))

with open(li_path, encoding="utf-8") as f:
    data = json.load(f)

with open(merged_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

if isinstance(data, list):
    count = len(data)
    print("Merged: {} items (list)".format(count))
else:
    keys = list(data.keys())
    print("Merged: dict with keys {}".format(keys))
    jobs = data.get("jobs", data.get("results", []))
    print("Jobs count: {}".format(len(jobs)))
