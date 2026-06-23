#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_cl_draft.py — Generate cover_letter_draft.md via claude CLI when none exists.
All context is passed inline so no file-read tools are needed.

Usage:
  python scripts/gen_cl_draft.py --job_folder <folder> --uid <uid>
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
USERS_DIR   = PROJECT_DIR / "users"
AGENTS_DIR  = PROJECT_DIR / ".claude" / "agents"
ANSI_RE     = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def _load_agent_spec() -> str:
    spec_path = AGENTS_DIR / "cover-letter.md"
    if not spec_path.exists():
        return ""
    raw = spec_path.read_text(encoding="utf-8")
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        return parts[2].strip() if len(parts) >= 3 else raw
    return raw


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job_folder", required=True)
    parser.add_argument("--uid", default="leon")
    args = parser.parse_args()

    job_dir  = USERS_DIR / args.uid / "output" / args.job_folder
    out_path = job_dir / "cover_letter_draft.md"

    if out_path.exists():
        print(f"CL_EXISTS: {out_path}", flush=True)
        return

    jd_file = job_dir / "jd_analysis.json"
    if not jd_file.exists():
        print(f"ERROR: jd_analysis.json not found at {jd_file}", file=sys.stderr)
        sys.exit(1)
    jd = json.loads(jd_file.read_text(encoding="utf-8"))

    group_id   = args.job_folder.split('_')[0]
    output_dir = USERS_DIR / args.uid / "output"
    cv_path    = output_dir / f"cv_parsed_{group_id}.json"
    if not cv_path.exists():
        candidates = sorted(output_dir.glob("cv_parsed_*.json"))
        cv_path = candidates[0] if candidates else None
    if not cv_path:
        print("ERROR: cv_parsed not found", file=sys.stderr)
        sys.exit(1)
    cv = json.loads(cv_path.read_text(encoding="utf-8"))

    story_bank_path = USERS_DIR / args.uid / "interview-prep" / "story-bank.md"
    story_bank = story_bank_path.read_text(encoding="utf-8") if story_bank_path.exists() else ""

    agent_spec = _load_agent_spec()
    today      = date.today().strftime("%d %B %Y")

    cv_info = "\n".join(f"{k}: {cv.get(k, '')}"
                        for k in ("name", "email", "phone", "linkedin", "location"))

    prompt = (
        f"{agent_spec}\n\n"
        f"---\n\n"
        f"Today's date: {today}\n"
        f"job_folder: {args.job_folder}\n\n"
        f"## JD Analysis\n```json\n{json.dumps(jd, ensure_ascii=False, indent=2)}\n```\n\n"
        f"## CV Personal Info\n{cv_info}\n\n"
        f"## CV Experience\n```json\n"
        f"{json.dumps(cv.get('experience', []), ensure_ascii=False, indent=2)}\n```\n\n"
    )
    if story_bank:
        prompt += f"## Story Bank\n{story_bank}\n\n"
    prompt += (
        "Generate the cover letter now. "
        "Output ONLY the markdown content starting with '# Cover Letter —'. "
        "Do not include any explanation, preamble, or text outside the markdown block."
    )

    claude_bin = shutil.which('claude') or 'claude'
    company    = jd.get("company", "")
    title      = jd.get("title", "")
    print(f"Generating cover letter for {company} — {title}…", flush=True)

    # Pass prompt via stdin to avoid Windows 8191-char command-line limit
    proc = subprocess.Popen(
        [claude_bin, '--print',
         '--model', 'claude-opus-4-8',
         '--disallowedTools',
         'Read,Glob,Grep,Write,Edit,WebFetch,WebSearch,TodoWrite,TodoRead,Bash'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(PROJECT_DIR), text=True,
        encoding='utf-8', errors='replace',
    )

    stdout, stderr = proc.communicate(input=prompt)

    if proc.returncode != 0:
        print(f"ERROR: claude exited {proc.returncode}", file=sys.stderr)
        if stderr:
            print(stderr[:500], file=sys.stderr)
        sys.exit(1)

    # Strip ANSI codes and find the markdown block
    clean = ANSI_RE.sub('', stdout)
    # Extract from first '# Cover Letter' onwards
    match = re.search(r'(#\s*Cover Letter.+)', clean, re.DOTALL)
    content = match.group(1).strip() if match else clean.strip()

    if not content:
        print("ERROR: empty response from claude", file=sys.stderr)
        sys.exit(1)

    out_path.write_text(content + "\n", encoding="utf-8")
    print(f"CL_WRITTEN_OK: {out_path}", flush=True)


if __name__ == "__main__":
    main()
