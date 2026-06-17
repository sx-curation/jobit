#!/usr/bin/env python3
"""Debug: show raw result structure from one search."""

import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))
from linkedin_search import search_jobs

result = search_jobs(
    keywords="PMO Manager",
    location="Germany",
    date_posted="past_month",
    max_pages=1,
    timeout=180,
)

print("TYPE:", type(result))
print("KEYS:", list(result.keys()) if isinstance(result, dict) else "N/A")
# Print first 3000 chars
text = json.dumps(result, ensure_ascii=False, indent=2)
print(text[:3000])
