import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import os
for d in os.listdir("output"):
    p = f"output/{d}/jd_analysis.json"
    if not os.path.exists(p): continue
    data = json.load(open(p, encoding="utf-8"))
    for field in ["missing_skills","matching_skills","key_requirements","recommended_emphasis"]:
        v = data.get(field)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            print(f"{d}: {field} is list-of-dict, first item keys: {list(v[0].keys())}")