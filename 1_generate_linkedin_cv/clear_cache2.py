import json
from pathlib import Path
jd_path = Path("users/leon/output/group-pdm_UP42_Product-Marketing-Manager-mfx_20260602/jd_analysis.json")
jd = json.loads(jd_path.read_text(encoding="utf-8-sig"))
jd.pop("exp_optimized", None)
jd.pop("default_answers", None)
jd_path.write_text(json.dumps(jd, ensure_ascii=False, indent=2), encoding="utf-8")
print("Cache cleared, match_score:", jd.get("match_score"))