#!/usr/bin/env python3
"""
scripts/migrate_legacy_jd_fields.py

补全旧格式 jd_analysis.json 中缺少的三个字段：
  - decision_score  (M0a，7 维综合评分，基于现有数据计算 4/7 维)
  - legitimacy      (M4，7 维合法性评分，基于现有数据计算 6/7 维)
  - missing_skills  (M5，结构化对象，含 severity)

只追加新字段，不修改现有字段。原子写入（.tmp → rename）。

用法：
  python scripts/migrate_legacy_jd_fields.py --uid leon
  python scripts/migrate_legacy_jd_fields.py --uid leon --dry-run
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

TODAY = datetime.now(timezone.utc)

# ── Constants ──────────────────────────────────────────────────────────────────
PREFERRED_LOCATIONS = [
    "Hamburg", "Berlin", "Munich", "Frankfurt",
    "Düsseldorf", "Köln", "Lüneburg", "Remote",
]

COMPANY_WHITELIST = {
    "SAP", "Siemens", "Capgemini", "Hapag-Lloyd", "Aldi", "BMW",
    "Mercedes-Benz", "Bosch", "Deutsche Bank", "Allianz", "BASF", "Bayer",
    "Volkswagen", "DHL", "Lufthansa", "Zalando", "Otto", "Beiersdorf",
    "Airbus", "Daimler", "Continental",
}

SEVERITY_MAP = {
    "high":   "hard_blocker",
    "medium": "learnable",
    "low":    "nice_to_have",
}


# ── Helpers ────────────────────────────────────────────────────────────────────
def days_since(date_str: str) -> int | None:
    """Parse ISO 8601 or YYYY-MM-DD date string, return days since that date."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str[:19], fmt).replace(tzinfo=timezone.utc)
            return max(0, (TODAY - dt).days)
        except ValueError:
            continue
    # Try "YYYY-MM-DD" prefix
    m = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return max(0, (TODAY - dt).days)
        except ValueError:
            pass
    return None


def posting_freshness_score(days: int | None) -> int:
    if days is None:
        return 50
    if days <= 7:
        return 100
    if days <= 30:
        return 80
    if days <= 90:
        return 50
    return 20


def location_fit_score(location: str) -> int:
    if not location:
        return 50
    loc_lower = location.lower()
    for pref in PREFERRED_LOCATIONS:
        if pref.lower() in loc_lower:
            return 100
    if "germany" in loc_lower or "deutschland" in loc_lower:
        return 70
    if "remote" in loc_lower:
        return 100
    return 40


def company_verifiable_score(company: str, url: str) -> int:
    if not company:
        return 40
    company_clean = company.strip()
    # Check whitelist (partial match)
    for wl in COMPANY_WHITELIST:
        if wl.lower() in company_clean.lower():
            return 100
    # Has a valid URL → verifiable
    if url and url.startswith("http"):
        return 80
    return 40


def requirements_realistic_score(required_skills: list) -> int:
    n = len(required_skills) if required_skills else 0
    if n <= 10:
        return 90
    if n <= 15:
        return 70
    return 40


def contact_info_score(url: str) -> int:
    return 90 if (url and url.startswith("http")) else 20


def jd_quality_score(jd: dict) -> int:
    """Proxy: required_total from scoring * 8, capped at 90."""
    scoring = jd.get("scoring") or {}
    required_total = scoring.get("required_total", 0) or 0
    if required_total == 0:
        # Fallback: count required_skills list
        required_total = len(jd.get("required_skills") or [])
    return min(90, max(40, required_total * 8))


# ── Field builders ─────────────────────────────────────────────────────────────
def build_missing_skills(jd: dict) -> list:
    """Convert old-format missing_skills (strings) to structured objects.
    Uses gaps[] for the 2 files that have it; otherwise severity='unknown'.
    """
    raw_ms = jd.get("missing_skills") or []
    gaps   = jd.get("gaps") or []

    # Build a lookup: gap text → gap object
    gap_lookup: dict[str, dict] = {}
    for g in gaps:
        key = (g.get("gap") or "").strip().lower()
        if key:
            gap_lookup[key] = g

    result = []
    for item in raw_ms:
        if isinstance(item, dict):
            # Already structured (shouldn't happen for old files, but be safe)
            result.append(item)
            continue

        skill_str = str(item).strip()
        if not skill_str:
            continue

        # Try to match against gaps[]
        best_gap = None
        best_ratio = 0.0
        for gap_key, gap_obj in gap_lookup.items():
            ratio = SequenceMatcher(None, skill_str.lower(), gap_key).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_gap = gap_obj

        if best_gap and best_ratio >= 0.6:
            raw_sev = (best_gap.get("severity") or "").lower()
            severity = SEVERITY_MAP.get(raw_sev, "unknown")
            result.append({
                "skill":             skill_str,
                "severity":          severity,
                "weeks_to_acquire":  None,
                "adjacent_in_cv":    None,
                "mitigation":        best_gap.get("note") or None,
            })
        else:
            result.append({
                "skill":             skill_str,
                "severity":          "unknown",
                "weeks_to_acquire":  None,
                "adjacent_in_cv":    None,
                "mitigation":        None,
            })

    return result


def build_gap_summary(missing_skills: list) -> dict:
    hard = sum(1 for s in missing_skills if s.get("severity") == "hard_blocker")
    learnable = sum(1 for s in missing_skills if s.get("severity") == "learnable")
    # 'unknown' + 'nice_to_have' → nice_to_have bucket
    nth = sum(1 for s in missing_skills if s.get("severity") in ("nice_to_have", "unknown"))
    return {
        "hard_blockers": hard,
        "nice_to_have":  nth,
        "learnable":     learnable,
        "blocker_flag":  hard > 0,
    }


def build_decision_score(jd: dict) -> tuple[int, dict, list]:
    """Returns (score, signals_dict, notes_list)."""
    company_info = jd.get("company_info") or {}
    location_raw = (
        company_info.get("location")
        or jd.get("location")
        or ""
    )
    analyzed_at = jd.get("analyzed_at") or ""
    days = days_since(analyzed_at)

    level_fit       = 50   # JD text unavailable
    location_fit    = location_fit_score(location_raw)
    work_mode_fit   = 50   # JD text unavailable
    freshness       = posting_freshness_score(days)
    compensation    = 50   # no salary info in old format
    job_family_fit  = 90   # already routed to correct group
    industry_fit    = 50   # company industry not structured

    score = round(
        level_fit      * 0.25
        + location_fit * 0.20
        + work_mode_fit * 0.15
        + freshness     * 0.10
        + compensation  * 0.10
        + job_family_fit * 0.15
        + industry_fit  * 0.05
    )

    signals = {
        "level_fit":        level_fit,
        "location_fit":     location_fit,
        "work_mode_fit":    work_mode_fit,
        "posting_freshness": freshness,
        "compensation_fit": compensation,
        "job_family_fit":   job_family_fit,
        "industry_fit":     industry_fit,
    }
    notes = [
        "decision_score computed from limited historical data (JD text unavailable); "
        "level_fit/work_mode_fit/industry_fit set to neutral (50)"
    ]
    if days is not None:
        notes.append(f"Analyzed {days} days ago (posting_freshness={freshness})")
    if location_raw:
        notes.append(f"Location '{location_raw}' → location_fit={location_fit}")

    return score, signals, notes


def build_legitimacy(jd: dict) -> dict:
    url         = jd.get("url") or ""
    company     = jd.get("company") or ""
    analyzed_at = jd.get("analyzed_at") or ""
    req_skills  = jd.get("required_skills") or []
    days        = days_since(analyzed_at)

    jd_quality         = jd_quality_score(jd)
    freshness          = posting_freshness_score(days)
    company_verif      = company_verifiable_score(company, url)
    req_realistic      = requirements_realistic_score(req_skills)
    contact            = contact_info_score(url)
    repost_freshness   = 100  # no raw_results available for repost check
    company_stability  = 60   # WebSearch not available

    score = round(
        jd_quality        * 0.25
        + freshness       * 0.15
        + company_verif   * 0.15
        + req_realistic   * 0.10
        + contact         * 0.10
        + repost_freshness * 0.15
        + company_stability * 0.10
    )

    if score >= 75:
        verdict = "HIGH_CONFIDENCE"
    elif score >= 50:
        verdict = "CAUTION"
    else:
        verdict = "SUSPICIOUS"

    return {
        "verdict": verdict,
        "score":   score,
        "signals": {
            "jd_quality":             jd_quality,
            "posting_freshness":      freshness,
            "company_verifiable":     company_verif,
            "requirements_realistic": req_realistic,
            "contact_info_present":   contact,
            "repost_freshness":       repost_freshness,
            "company_stability":      company_stability,
        },
        "red_flags": [],
        "repost_info": {
            "detected":         False,
            "count":            0,
            "first_seen_batch": None,
            "days_since_first": None,
            "similar_titles":   [],
        },
        "hiring_signal": {
            "verdict":              "unknown",
            "evidence":             None,
            "search_executed":      False,
            "search_skipped_reason": (
                "WebSearch not available for historical data migration; "
                "company_stability set to neutral 60"
            ),
        },
    }


# ── Main ───────────────────────────────────────────────────────────────────────
def process_file(jd_path: Path, dry_run: bool) -> str:
    try:
        raw = jd_path.read_text(encoding="utf-8-sig")
        jd  = json.loads(raw)
    except Exception as e:
        return f"ERROR reading {jd_path.name}: {e}"

    # Only process old-format files (missing decision_score)
    if "decision_score" in jd:
        return f"SKIP {jd_path.parent.name} (already has decision_score)"

    # 1. missing_skills → structured
    new_ms       = build_missing_skills(jd)
    gap_summary  = build_gap_summary(new_ms)

    # 2. decision_score
    d_score, d_signals, d_notes = build_decision_score(jd)

    # 3. legitimacy
    legitimacy = build_legitimacy(jd)

    # 4. matched_skills from strengths (if missing)
    if not jd.get("matched_skills") and jd.get("strengths"):
        jd["matched_skills"] = jd["strengths"]

    # Apply updates (only add, never remove existing fields)
    jd["missing_skills"]         = new_ms
    jd["gap_summary"]            = gap_summary
    jd["decision_score"]         = d_score
    jd["decision_signals"]       = d_signals
    jd["decision_notes"]         = d_notes
    jd["legitimacy"]             = legitimacy
    # These fields default to empty if absent (for server.py compatibility)
    jd.setdefault("customization_potential", {
        "current_match_score": jd.get("match_score", -1),
        "estimated_max_score": -1,
        "score_gap": 0,
        "top_changes": [],
    })
    jd.setdefault("culture_keywords", [])
    jd.setdefault("job_family", {
        "detected_group": None, "confidence": 0.0,
        "matched_title": None, "cv_group_match": False,
        "group_mismatch_warning": None,
    })

    if dry_run:
        return (f"DRY-RUN {jd_path.parent.name}: "
                f"d_score={d_score} leg_score={legitimacy['score']} "
                f"({legitimacy['verdict']}) ms={len(new_ms)} skills")

    # Atomic write
    tmp = jd_path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(jd, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(jd_path)
    except Exception as e:
        tmp.unlink(missing_ok=True)
        return f"ERROR writing {jd_path.name}: {e}"

    return (f"OK {jd_path.parent.name}: "
            f"d_score={d_score} leg={legitimacy['score']}({legitimacy['verdict']}) "
            f"ms={len(new_ms)} sev_unknown={sum(1 for s in new_ms if s['severity']=='unknown')}")


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy jd_analysis.json fields")
    parser.add_argument("--uid",     default="leon")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    output_dir   = project_root / "users" / args.uid / "output"

    if not output_dir.exists():
        print(f"ERROR: output dir not found: {output_dir}", file=sys.stderr)
        sys.exit(1)

    jd_files = sorted(output_dir.rglob("jd_analysis.json"))
    to_process = [f for f in jd_files
                  if "decision_score" not in f.read_text(encoding="utf-8-sig", errors="replace")]

    print(f"Found {len(jd_files)} jd_analysis.json files, {len(to_process)} need migration.")
    if args.dry_run:
        print("(dry-run mode — no files will be written)\n")

    ok = skip = err = 0
    for jd_path in to_process:
        result = process_file(jd_path, args.dry_run)
        print(f"  {result}")
        if result.startswith("OK") or result.startswith("DRY"):
            ok += 1
        elif result.startswith("SKIP"):
            skip += 1
        else:
            err += 1

    print(f"\nDone. OK={ok}  SKIP={skip}  ERR={err}")

    if not args.dry_run and ok > 0:
        # Touch job_summary.md to invalidate server cache
        summary = output_dir / "job_summary.md"
        if summary.exists():
            summary.touch()
            print(f"Touched {summary} to invalidate server cache.")


if __name__ == "__main__":
    main()
