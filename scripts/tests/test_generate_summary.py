"""
Unit tests for generate_summary.py

Covers: fmt_list, extract_group_id, score_bar, cross_source_dedup,
        build_markdown, load_last_seen.

All functions are pure or accept a Path argument — no global state patching needed.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import generate_summary as gs  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────────

def _rec(company="Acme", title="Dev", score=80, source="linkedin",
         url="https://example.com", folder="group-test_Acme_Dev_20240101",
         date="2024-01-01", missing=None, emphasis=None, remark=""):
    return {
        "company":              company,
        "title":                title,
        "match_score":          score,
        "_source":              source,
        "url":                  url,
        "_folder":              folder,
        "_analyzed_date":       date,
        "_last_seen":           "",
        "_remark":              remark,
        "missing_skills":       missing or [],
        "recommended_emphasis": emphasis or [],
    }


# ── TestFmtList ─────────────────────────────────────────────────────────────────

class TestFmtList:
    def test_empty_returns_dash(self):
        assert gs.fmt_list([]) == "—"

    def test_single_item(self):
        assert gs.fmt_list(["Python"]) == "Python"

    def test_truncates_at_max_items_with_plus_n(self):
        result = gs.fmt_list(["A", "B", "C", "D"], max_items=3)
        assert "+1" in result
        assert "A" in result
        assert "D" not in result

    def test_dict_items_use_skill_key(self):
        result = gs.fmt_list([{"skill": "Python"}])
        assert result == "Python"

    def test_pipe_in_item_replaced_with_slash(self):
        result = gs.fmt_list(["A|B"])
        assert "|" not in result
        assert "/" in result

    def test_custom_max_items(self):
        result = gs.fmt_list(["A", "B", "C", "D", "E"], max_items=2)
        assert "+3" in result


# ── TestExtractGroupId ──────────────────────────────────────────────────────────

class TestExtractGroupId:
    def test_group_prefix_extracted(self):
        assert gs.extract_group_id("group-test_Acme_Dev_20240101") == "group-test"

    def test_non_group_folder_returns_dash(self):
        assert gs.extract_group_id("Acme_Dev_20240101") == "—"

    def test_group_with_hyphen(self):
        assert gs.extract_group_id("group-data-science_Company_Role_20240101") == "group-data-science"


# ── TestScoreBar ────────────────────────────────────────────────────────────────

class TestScoreBar:
    def test_green_at_75_and_above(self):
        assert gs.score_bar(75) == "🟢"
        assert gs.score_bar(100) == "🟢"

    def test_yellow_60_to_74(self):
        assert gs.score_bar(60) == "🟡"
        assert gs.score_bar(74) == "🟡"

    def test_orange_45_to_59(self):
        assert gs.score_bar(45) == "🟠"
        assert gs.score_bar(59) == "🟠"

    def test_red_below_45(self):
        assert gs.score_bar(44) == "🔴"
        assert gs.score_bar(0) == "🔴"


# ── TestCrossSourceDedup ────────────────────────────────────────────────────────

class TestCrossSourceDedup:
    def test_single_record_group_unchanged(self):
        records = [_rec("Acme", "Dev", score=85)]
        result = gs.cross_source_dedup(records)
        assert len(result) == 1
        assert result[0]["match_score"] == 85

    def test_linkedin_preferred_over_stepstone(self):
        li = _rec("Acme", "Dev", source="linkedin",  score=80)
        st = _rec("Acme", "Dev", source="stepstone", score=80)
        result = gs.cross_source_dedup([li, st])
        assert len(result) == 1
        assert result[0]["_source"] == "linkedin"

    def test_url_filled_from_stepstone_when_linkedin_missing(self):
        li = _rec("Acme", "Dev", source="linkedin",  url="",                    score=80)
        st = _rec("Acme", "Dev", source="stepstone", url="https://st.example", score=80)
        result = gs.cross_source_dedup([li, st])
        assert result[0]["url"] == "https://st.example"

    def test_remark_set_to_source_duplicate(self):
        li = _rec("Acme", "Dev", source="linkedin")
        st = _rec("Acme", "Dev", source="stepstone")
        result = gs.cross_source_dedup([li, st])
        assert result[0]["_remark"] == "数据源重复"

    def test_same_source_keeps_highest_score(self):
        low  = _rec("Acme", "Dev", source="linkedin", score=60)
        high = _rec("Acme", "Dev", source="linkedin", score=90)
        result = gs.cross_source_dedup([low, high])
        assert len(result) == 1
        assert result[0]["match_score"] == 90

    def test_earliest_date_preserved_across_duplicates(self):
        r1 = _rec("Acme", "Dev", source="linkedin",  date="2024-03-01")
        r2 = _rec("Acme", "Dev", source="stepstone", date="2024-01-15")
        result = gs.cross_source_dedup([r1, r2])
        assert result[0]["_analyzed_date"] == "2024-01-15"

    def test_case_insensitive_matching(self):
        r1 = _rec("acme corp", "senior dev", source="linkedin")
        r2 = _rec("Acme Corp", "Senior Dev", source="stepstone")
        result = gs.cross_source_dedup([r1, r2])
        assert len(result) == 1


# ── TestBuildMarkdown ───────────────────────────────────────────────────────────

class TestBuildMarkdown:
    def test_output_starts_with_header(self):
        md = gs.build_markdown([_rec()])
        assert md.startswith("# Job Analysis Summary")

    def test_row_count_matches_records(self):
        records = [_rec("A", "Dev"), _rec("B", "Dev"), _rec("C", "Dev")]
        md = gs.build_markdown(records)
        # Count data rows (lines starting with "| 1 |", "| 2 |", "| 3 |")
        data_rows = [l for l in md.splitlines() if l.startswith("| ") and not l.startswith("| #") and not l.startswith("|---")]
        assert len(data_rows) == 3

    def test_missing_skills_formatted_as_fmt_list(self):
        rec = _rec(missing=["Kubernetes", "Terraform", "Helm", "ArgoCD"])
        md = gs.build_markdown([rec])
        # fmt_list with max_items=3 → "+1" should appear
        assert "+1" in md

    def test_folder_link_in_score_cell(self):
        rec = _rec(folder="group-test_Acme_Dev_20240101", score=80)
        md = gs.build_markdown([rec])
        assert "group-test_Acme_Dev_20240101/jd_analysis.json" in md

    def test_empty_records_no_data_rows(self):
        md = gs.build_markdown([])
        data_rows = [l for l in md.splitlines()
                     if l.startswith("| ") and not l.startswith("| #") and not l.startswith("|---")]
        assert len(data_rows) == 0

    def test_sorted_by_score_descending(self):
        records = [_rec("Low",  "Dev", score=50),
                   _rec("High", "Dev", score=95),
                   _rec("Mid",  "Dev", score=70)]
        md = gs.build_markdown(records)
        lines = [l for l in md.splitlines() if l.startswith("| ")]
        # Find the data rows only
        data = [l for l in lines if not l.startswith("| #") and not l.startswith("|---")]
        assert "High" in data[0]
        assert "Low"  in data[-1]


# ── TestLoadLastSeen ────────────────────────────────────────────────────────────

class TestLoadLastSeen:
    def test_no_history_file_returns_empty_dicts(self, tmp_path):
        by_id, by_ct = gs.load_last_seen(tmp_path)
        assert by_id == {}
        assert by_ct == {}

    def test_by_id_lookup(self, tmp_path):
        history = {
            "seen_jobs": {
                "123": {"company": "Acme", "title": "Dev",
                        "last_seen": "2024-05-01", "first_seen": "2024-04-01"}
            }
        }
        (tmp_path / "search_history.json").write_text(
            json.dumps(history), encoding="utf-8")
        by_id, _ = gs.load_last_seen(tmp_path)
        assert by_id["123"] == "2024-05-01"

    def test_by_company_title_lookup(self, tmp_path):
        history = {
            "seen_jobs": {
                "456": {"company": "BetaCorp", "title": "Engineer",
                        "last_seen": "2024-06-01", "first_seen": "2024-05-01"}
            }
        }
        (tmp_path / "search_history.json").write_text(
            json.dumps(history), encoding="utf-8")
        _, by_ct = gs.load_last_seen(tmp_path)
        assert by_ct[("betacorp", "engineer")] == "2024-06-01"

    def test_fallback_to_first_seen_when_last_seen_missing(self, tmp_path):
        history = {
            "seen_jobs": {
                "789": {"company": "Zeta", "title": "Lead",
                        "first_seen": "2024-03-10"}
            }
        }
        (tmp_path / "search_history.json").write_text(
            json.dumps(history), encoding="utf-8")
        by_id, _ = gs.load_last_seen(tmp_path)
        assert by_id["789"] == "2024-03-10"
