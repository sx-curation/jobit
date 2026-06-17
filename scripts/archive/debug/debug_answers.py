import json, shutil, subprocess
from pathlib import Path

uid = "leon"
job_folder = "group-pdm_UP42_Product-Marketing-Manager-mfx_20260602"
user_dir = Path("users") / uid
jd = json.loads(open(user_dir / "output" / job_folder / "jd_analysis.json", encoding="utf-8-sig").read())

company = jd.get("company", "UP42")
title = jd.get("title", "Product Marketing Manager")
prompt = (
    f"Generate 5 interview answers for: {title} at {company}.\n"
    "Return ONLY valid JSON with no markdown, no code fences:\n"
    '{"default_answers":[{"question":"...","answer":"..."}]}\n'
    "Fill in 5 questions and answers."
)

claude_bin = shutil.which("claude") or "claude"
result = subprocess.run(
    [claude_bin, "-p", prompt],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    cwd=str(user_dir), text=True, encoding="utf-8", errors="replace", timeout=120
)
print("RETURN CODE:", result.returncode)
print("OUTPUT:")
print(result.stdout[:1000])