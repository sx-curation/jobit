#!/usr/bin/env python3
"""
scripts/translate_skills.py

Scan all jd_analysis.json files, detect German text in `recommended_emphasis`
and `missing_skills`, and translate them to English via a single claude -p call.

Usage:
  python scripts/translate_skills.py
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR  = PROJECT_DIR / "output"

_DE_PATTERN = re.compile(
    r'\b(und|für|hervorheben|betonen|Betone|nennen|zeigen|kommunizieren'
    r'|Kenntnisse|Erfahrung|Erfahrungen|Fähigkeiten|Fähigkeit'
    r'|Zertifizierung|Kompetenz|Sprachkenntnisse'
    r'|Deutschkenntnisse|Englischkenntnisse'
    r'|Zielgruppen|Kundensegmentierung|Datenanalyse'
    r'|explizit|konkret|direkt|nachweisen)\b',
)

def is_german(text: str) -> bool:
    return bool(_DE_PATTERN.search(text))


def collect_german_entries(output_dir: Path):
    """Return list of (jd_file, field_name, index, original_text) for German entries."""
    entries = []
    for jd_file in sorted(output_dir.glob("*/jd_analysis.json")):
        try:
            data = json.loads(jd_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        for field in ("recommended_emphasis", "missing_skills"):
            items = data.get(field, [])
            for i, item in enumerate(items):
                if isinstance(item, str) and is_german(item):
                    entries.append((jd_file, field, i, item))
    return entries


BATCH_SIZE = 25
_TMP_IN  = PROJECT_DIR / "output" / "temp" / "_translate_input.json"
_TMP_OUT = PROJECT_DIR / "output" / "temp" / "_translate_output.json"

def translate_batch(texts: list[str]) -> list[str] | None:
    """Translate all texts in batches via claude -p (file-based I/O)."""
    all_results: list[str] = []
    claude_bin = shutil.which("claude") or "claude"

    for i in range(0, len(texts), BATCH_SIZE):
        chunk = texts[i:i + BATCH_SIZE]
        _TMP_IN.write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding="utf-8")
        _TMP_OUT.unlink(missing_ok=True)

        prompt = (
            f"Read the file {_TMP_IN} which contains a JSON array of strings. "
            "Translate each string to English. Preserve technical terms and tool names. "
            "Keep each item concise (under 120 chars). "
            "Print ONLY a valid JSON array with the same number of items in the same order. "
            "No other text."
        )
        try:
            result = subprocess.run(
                [claude_bin, "-p", prompt],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120,
                cwd=str(PROJECT_DIR),
            )
            output = result.stdout.strip()
            match = re.search(r'\[.*\]', output, re.DOTALL)
            if not match:
                print(f"[WARN] Batch {i//BATCH_SIZE+1}: no JSON array in stdout", file=sys.stderr)
                print(f"       stdout: {output[:300]}", file=sys.stderr)
                return None
            batch_result = json.loads(match.group(0))
            if len(batch_result) != len(chunk):
                print(f"[WARN] Batch {i//BATCH_SIZE+1}: expected {len(chunk)}, got {len(batch_result)}", file=sys.stderr)
                return None
            all_results.extend(batch_result)
            print(f"  Batch {i//BATCH_SIZE+1}/{(len(texts)-1)//BATCH_SIZE+1}: {len(chunk)} items translated.")
        except Exception as e:
            print(f"[WARN] Batch {i//BATCH_SIZE+1} failed: {e}", file=sys.stderr)
            return None

    _TMP_IN.unlink(missing_ok=True)
    _TMP_OUT.unlink(missing_ok=True)
    return all_results


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    print("Scanning for German text in jd_analysis.json files...")
    entries = collect_german_entries(OUTPUT_DIR)

    if not entries:
        print("No German entries found. Nothing to translate.")
        return

    print(f"Found {len(entries)} German entries across {len({e[0] for e in entries})} files.")

    texts = [e[3] for e in entries]
    print(f"Translating {len(texts)} entries via claude...")
    translations = translate_batch(texts)

    if translations is None or len(translations) != len(texts):
        print("[ERROR] Translation failed or returned wrong count. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Group updates by file
    file_updates: dict[Path, dict] = {}
    for (jd_file, field, idx, _), translation in zip(entries, translations):
        if jd_file not in file_updates:
            file_updates[jd_file] = {}
        if field not in file_updates[jd_file]:
            file_updates[jd_file][field] = {}
        file_updates[jd_file][field][idx] = translation

    # Apply updates
    updated_files = 0
    for jd_file, fields in file_updates.items():
        try:
            data = json.loads(jd_file.read_text(encoding="utf-8"))
            for field, idx_map in fields.items():
                items = data.get(field, [])
                for idx, translation in idx_map.items():
                    if idx < len(items):
                        items[idx] = translation
                data[field] = items
            jd_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            updated_files += 1
        except Exception as e:
            print(f"[WARN] Failed to update {jd_file}: {e}", file=sys.stderr)

    print(f"Translated {len(entries)} entries in {updated_files} files.")


if __name__ == "__main__":
    main()
