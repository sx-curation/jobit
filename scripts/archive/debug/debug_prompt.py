import json
from pathlib import Path

uid = "leon"
job_folder = "group-pdm_UP42_Product-Marketing-Manager-mfx_20260602"
user_dir = Path("users") / uid
jd = json.loads((user_dir / "output" / job_folder / "jd_analysis.json").read_text(encoding="utf-8-sig"))
cv = json.loads((user_dir / "output" / "cv_parsed_group-pdm.json").read_text(encoding="utf-8-sig"))

matched_skills = jd.get("matched_skills", [])
skills_str = ", ".join(matched_skills[:10])

for exp in cv.get("experience", [])[:1]:
    company = (exp.get("company") or "").strip()
    bullets = exp.get("bullets", [])
    desc = "\n".join(f"- {b}" for b in bullets)
    print(f"Company: {company}")
    print(f"Bullets count: {len(bullets)}")
    print(f"desc preview: {desc[:200]}")
    print(f"skills_str preview: {skills_str[:100]}")