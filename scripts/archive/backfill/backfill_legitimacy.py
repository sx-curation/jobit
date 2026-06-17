#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill_legitimacy.py — Estimate legitimacy scores for existing jd_analysis.json files.

Uses already-available fields (required_skills, decision_signals, company_info, url)
to derive a legitimacy score without WebSearch. Marks entries with "backfilled": true.

Usage:
  python scripts/backfill_legitimacy.py --uid leon
"""

import argparse
import json
from collections import Counter
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
USERS_DIR   = PROJECT_DIR / "users"


def _jd_quality(d: dict) -> int:
    n = len(d.get("required_skills", []))
    if n >= 5: return 90
    if n >= 3: return 60
    return 20


def _posting_freshness(d: dict) -> int:
    return d.get("decision_signals", {}).get("posting_freshness", 50)


def _company_verifiable(d: dict) -> int:
    src = (d.get("company_info") or {}).get("size_source", "unavailable")
    if src == "company_profile": return 100
    if src == "jd_text":         return 80
    return 40


def _requirements_realistic(d: dict) -> int:
    n = len(d.get("required_skills", []))
    if n <= 10: return 90
    if n <= 15: return 60
    return 30


def _contact_info_present(d: dict) -> int:
    return 90 if d.get("url") else 20


def compute_legitimacy(d: dict) -> dict:
    jd_q  = _jd_quality(d)
    fresh = _posting_freshness(d)
    verif = _company_verifiable(d)
    real  = _requirements_realistic(d)
    cip   = _contact_info_present(d)
    repost_fresh    = 100   # no batch scan — assume not reposted
    company_stab    = 60    # neutral default, no WebSearch

    score = round(
        jd_q   * 0.25 +
        fresh  * 0.15 +
        verif  * 0.15 +
        real   * 0.10 +
        cip    * 0.10 +
        repost_fresh * 0.15 +
        company_stab * 0.10
    )

    if score >= 75:   verdict = "HIGH_CONFIDENCE"
    elif score >= 50: verdict = "CAUTION"
    else:             verdict = "SUSPICIOUS"

    return {
        "verdict": verdict,
        "score": score,
        "signals": {
            "jd_quality":              jd_q,
            "posting_freshness":       fresh,
            "company_verifiable":      verif,
            "requirements_realistic":  real,
            "contact_info_present":    cip,
            "repost_freshness":        repost_fresh,
            "company_stability":       company_stab,
        },
        "red_flags": [],
        "repost_info": {
            "detected": False, "count": 0,
            "first_seen_batch": None, "days_since_first": None, "similar_titles": []
        },
        "hiring_signal": {
            "verdict": "unknown", "evidence": None,
            "search_executed": False,
            "search_skipped_reason": "backfill — no WebSearch performed"
        },
        "backfilled": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill legitimacy scores for existing jd_analysis.json files.")
    parser.add_argument("--uid", default="leon")
    args = parser.parse_args()

    output_dir = USERS_DIR / args.uid / "output"
    files = sorted(output_dir.glob("*/jd_analysis.json"))

    counts = Counter()
    errors = 0

    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            errors += 1
            continue

        # Skip if already has real legitimacy data (not backfilled)
        existing = d.get("legitimacy") or {}
        if existing and not existing.get("backfilled"):
            counts["skipped_real"] += 1
            continue

        d["legitimacy"] = compute_legitimacy(d)
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        counts[d["legitimacy"]["verdict"]] += 1

    total_written = sum(v for k, v in counts.items() if k != "skipped_real")
    print(f"Backfilled: {total_written} files  |  Errors: {errors}  |  Skipped (real data): {counts['skipped_real']}")
    print(f"Verdict distribution: HIGH_CONFIDENCE={counts['HIGH_CONFIDENCE']}  CAUTION={counts['CAUTION']}  SUSPICIOUS={counts['SUSPICIOUS']}")


if __name__ == "__main__":
    main()
