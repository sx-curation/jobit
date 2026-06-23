"""
Unit tests for search_state.py

Covers: quick_score, _expand_skill_tokens, dedup_and_sort,
        compute_offsets, save_raw_results, new_batch_id, _prune_seen_jobs.

All tests use the `state_paths` fixture which redirects module-level path
variables to a tmp_path so no real user data is touched.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import search_state  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def state_paths(tmp_path, monkeypatch):
    """Redirect search_state module-level path vars to tmp_path."""
    out = tmp_path / "output"
    tmp = out / "temp"
    tmp.mkdir(parents=True)
    monkeypatch.setattr(search_state, 'OUTPUT_DIR',      out)
    monkeypatch.setattr(search_state, 'TEMP_DIR',        tmp)
    monkeypatch.setattr(search_state, 'HISTORY_PATH',    out / "search_history.json")
    monkeypatch.setattr(search_state, 'BATCH_STATE_TSV', tmp / "batch_state.tsv")
    monkeypatch.setattr(search_state, 'LOCK_FILE',       tmp / ".search.lock")
    search_state._expand_skill_tokens.cache_clear()
    return tmp_path


def _minimal_config(min_score=20, max_display=30, groups=None):
    return {
        "job_search": {
            "max_display":            max_display,
            "min_score_for_analysis": min_score,
            "keyword_groups": groups or [{
                "group_id":    "group-test",
                "group_label": "Test",
                "cv_file":     "test.pdf",
                "primary_keywords": {"en": ["Python"], "de": []},
                "job_family":       {"en": [],          "de": []},
            }]
        }
    }


def _make_job(job_id, company="Acme", title="Dev", group_id="group-test",
              snippet="", description_full="", source="linkedin"):
    return {
        "job_id":               job_id,
        "company":              company,
        "title":                title,
        "_group_id":            group_id,
        "_keyword":             "python",
        "_source":              source,
        "description_snippet":  snippet,
        "description_full":     description_full,
    }


def _write_raw(state_paths, batch_id, jobs):
    tmp = state_paths / "output" / "temp"
    p = tmp / f"raw_results_{batch_id}.json"
    p.write_text(json.dumps(jobs), encoding="utf-8")


def _write_history(state_paths, h):
    p = state_paths / "output" / "search_history.json"
    p.write_text(json.dumps(h), encoding="utf-8")


def _today():
    return date.today().isoformat()


def _days_ago(n):
    return (date.today() - timedelta(days=n)).isoformat()


# ── TestQuickScore ───────────────────────────────────────────────────────────────

class TestQuickScore:
    def test_returns_50_when_no_skills(self):
        job = _make_job("1", snippet="Python developer needed")
        assert search_state.quick_score(job, []) == 50

    def test_title_hit_scores_5_per_skill(self):
        job = _make_job("1", title="Python Developer",
                        snippet="A" * 200)  # long snippet, no python there
        score = search_state.quick_score(job, ["python"])
        assert score == 5

    def test_text_hit_scores_2_per_skill(self):
        job = _make_job("1", title="Java Developer",
                        snippet="We use Python extensively. " + "x" * 100)
        score = search_state.quick_score(job, ["python"])
        assert score == 2

    def test_snippet_fallback_when_short(self):
        # snippet < 100 chars → use description_full
        job = _make_job("1", title="Java Developer",
                        snippet="short",
                        description_full="We need a Python expert for this role.")
        score = search_state.quick_score(job, ["python"])
        assert score == 2

    def test_snippet_not_used_when_short(self):
        # snippet < 100 chars but description_full has no match either → score 0
        job = _make_job("1", title="Java Developer",
                        snippet="short Python reference",
                        description_full="Java and Kotlin only.")
        score = search_state.quick_score(job, ["python"])
        # falls back to full → no match → 0
        assert score == 0

    def test_capped_at_100(self):
        # 25 skills × 5 each = 125, should cap at 100
        skills = [f"skill{i}" for i in range(25)]
        title = " ".join(skills)
        job = _make_job("1", title=title, snippet="x" * 200)
        score = search_state.quick_score(job, skills)
        assert score == 100

    def test_token_expansion_slash(self):
        # "React/Vue" expands to tokens ["react/vue", "react", "vue"]
        # Title mentioning "react" should get a title-hit score of 5
        job = _make_job("1", title="React developer",
                        snippet="x" * 200)
        score = search_state.quick_score(job, ["React/Vue"])
        assert score == 5


# ── TestExpandSkillTokens ───────────────────────────────────────────────────────

class TestExpandSkillTokens:
    def setup_method(self):
        search_state._expand_skill_tokens.cache_clear()

    def test_includes_full_phrase_as_first(self):
        tokens = search_state._expand_skill_tokens("Machine Learning")
        assert tokens[0] == "machine learning"

    def test_splits_on_slash(self):
        tokens = search_state._expand_skill_tokens("A/B Testing")
        assert "a/b" in tokens or "testing" in tokens

    def test_splits_on_ampersand(self):
        tokens = search_state._expand_skill_tokens("Sales & Marketing")
        assert "sales" in tokens
        assert "marketing" in tokens

    def test_minimum_token_length_2(self):
        # single-char tokens should be excluded
        tokens = search_state._expand_skill_tokens("C / Java")
        assert "c" not in tokens or len([t for t in tokens if t == "c"]) == 0
        assert "java" in tokens


# ── TestDedup ───────────────────────────────────────────────────────────────────

class TestDedup:
    def test_rule_a_job_id_dedup(self, state_paths):
        """Job already seen by job_id + matching company/title → skipped."""
        h = {
            "batches": [{"batch_id": "20240101_001", "date": "2024-01-01",
                         "dedup_done": True, "raw_results_file": "x",
                         "fetched_total": 1}],
            "seen_jobs": {
                "123": {"company": "Acme", "title": "Dev",
                        "first_seen": _days_ago(5), "last_seen": _days_ago(5),
                        "needs_refetch": False}
            }
        }
        _write_history(state_paths, h)
        _write_raw(state_paths, "20240102_001", [_make_job("123")])

        cfg = _minimal_config()
        result = search_state.dedup_and_sort("20240102_001", cfg)

        assert result["skipped_duplicate"] == 1
        assert result["display_jobs"] == []

    def test_rule_b_company_title_dedup(self, state_paths):
        """Different job_id but same company+title → skipped."""
        h = {
            "batches": [],
            "seen_jobs": {
                "999": {"company": "Acme", "title": "Dev",
                        "first_seen": _days_ago(5), "last_seen": _days_ago(5),
                        "needs_refetch": False}
            }
        }
        _write_history(state_paths, h)
        _write_raw(state_paths, "20240102_001",
                   [_make_job("456", company="Acme", title="Dev")])

        cfg = _minimal_config()
        result = search_state.dedup_and_sort("20240102_001", cfg)

        assert result["skipped_duplicate"] == 1
        assert result["display_jobs"] == []

    def test_needs_refetch_bypass(self, state_paths):
        """needs_refetch=True → job passes dedup even if already seen."""
        h = {
            "batches": [],
            "seen_jobs": {
                "123": {"company": "Acme", "title": "Dev",
                        "first_seen": _days_ago(5), "last_seen": _days_ago(5),
                        "needs_refetch": True}
            }
        }
        _write_history(state_paths, h)
        _write_raw(state_paths, "20240102_001", [_make_job("123")])

        cfg = _minimal_config()
        result = search_state.dedup_and_sort("20240102_001", cfg)

        assert result["skipped_duplicate"] == 0
        assert len(result["display_jobs"]) == 1

    def test_intra_batch_dedup(self, state_paths):
        """Within same batch: same company+title → only first kept."""
        h = {"batches": [], "seen_jobs": {}}
        _write_history(state_paths, h)
        jobs = [
            _make_job("100", company="Acme", title="Dev"),
            _make_job("101", company="Acme", title="Dev"),  # duplicate
        ]
        _write_raw(state_paths, "20240102_001", jobs)

        cfg = _minimal_config()
        result = search_state.dedup_and_sort("20240102_001", cfg)

        assert len(result["display_jobs"]) == 1
        assert result["skipped_duplicate"] == 1

    def test_all_new_jobs_added_to_seen(self, state_paths):
        """Regression: ALL new jobs (including hidden low-score) enter seen_jobs."""
        h = {"batches": [], "seen_jobs": {}}
        _write_history(state_paths, h)
        # More jobs than max_display=2
        jobs = [_make_job(str(i), company=f"Co{i}", title="Dev") for i in range(5)]
        _write_raw(state_paths, "20240102_001", jobs)

        cfg = _minimal_config(max_display=2)
        result = search_state.dedup_and_sort("20240102_001", cfg)

        loaded = search_state.load_history()
        # All 5 jobs must be in seen_jobs, not just the 2 displayed
        assert len(loaded["seen_jobs"]) == 5

    def test_skip_analysis_flag(self, state_paths):
        """Jobs scoring below min_score get skip_analysis=True."""
        # Write cv_parsed with no skills so quick_score returns 0
        out = state_paths / "output"
        cv_parsed = out / "cv_parsed_group-test.json"
        cv_parsed.write_text(json.dumps({"skills": ["ZZZnonexistent"]}),
                             encoding="utf-8")

        h = {"batches": [], "seen_jobs": {}}
        _write_history(state_paths, h)
        job = _make_job("1", title="Java Engineer",
                        snippet="x" * 200, description_full="Java only")
        _write_raw(state_paths, "20240102_001", [job])

        cfg = _minimal_config(min_score=20)
        result = search_state.dedup_and_sort("20240102_001", cfg)

        assert result["display_jobs"][0]["skip_analysis"] is True


# ── TestComputeOffsets ──────────────────────────────────────────────────────────

class TestComputeOffsets:
    def test_same_day_accumulates(self, state_paths):
        today = _today()
        h = {
            "batches": [
                {"batch_id": "x_001", "date": today, "dedup_done": True,
                 "fetched_per_keyword": {"Python": 25}},
                {"batch_id": "x_002", "date": today, "dedup_done": True,
                 "fetched_per_keyword": {"Python": 15}},
            ],
            "seen_jobs": {}
        }
        _write_history(state_paths, h)
        cfg = _minimal_config()
        offsets = search_state.compute_offsets(cfg)
        assert offsets["Python"] == 40

    def test_cross_day_resets(self, state_paths):
        yesterday = _days_ago(1)
        h = {
            "batches": [
                {"batch_id": "x_001", "date": yesterday, "dedup_done": True,
                 "fetched_per_keyword": {"Python": 50}},
            ],
            "seen_jobs": {}
        }
        _write_history(state_paths, h)
        cfg = _minimal_config()
        offsets = search_state.compute_offsets(cfg)
        assert offsets["Python"] == 0


# ── TestSaveRawResults ──────────────────────────────────────────────────────────

class TestSaveRawResults:
    def test_creates_batch_entry(self, state_paths):
        h = {"batches": [], "seen_jobs": {}}
        _write_history(state_paths, h)
        jobs = [_make_job("1")]
        search_state.save_raw_results("20240102_001", jobs)

        loaded = search_state.load_history()
        assert len(loaded["batches"]) == 1
        assert loaded["batches"][0]["batch_id"] == "20240102_001"
        assert loaded["batches"][0]["fetched_total"] == 1
        assert loaded["batches"][0]["dedup_done"] is False

    def test_atomic_write(self, state_paths):
        """Temp .tmp file should not exist after successful write."""
        h = {"batches": [], "seen_jobs": {}}
        _write_history(state_paths, h)
        search_state.save_raw_results("20240102_001", [_make_job("1")])

        tmp_file = state_paths / "output" / "temp" / "raw_results_20240102_001.tmp"
        assert not tmp_file.exists()
        real_file = state_paths / "output" / "temp" / "raw_results_20240102_001.json"
        assert real_file.exists()

    def test_updates_existing_batch(self, state_paths):
        """Re-saving same batch_id updates fetched_total, does not add duplicate."""
        h = {
            "batches": [{"batch_id": "20240102_001", "date": _today(),
                         "dedup_done": False, "fetched_total": 1,
                         "raw_results_file": "x"}],
            "seen_jobs": {}
        }
        _write_history(state_paths, h)
        search_state.save_raw_results("20240102_001", [_make_job("1"), _make_job("2")])

        loaded = search_state.load_history()
        assert len(loaded["batches"]) == 1
        assert loaded["batches"][0]["fetched_total"] == 2


# ── TestNewBatchId ──────────────────────────────────────────────────────────────

class TestNewBatchId:
    def test_first_batch_today(self):
        today_str = date.today().strftime("%Y%m%d")
        h = {"batches": [], "seen_jobs": {}}
        bid = search_state.new_batch_id(h)
        assert bid == f"{today_str}_001"

    def test_second_batch_today(self):
        today = _today()
        today_str = date.today().strftime("%Y%m%d")
        h = {"batches": [{"batch_id": f"{today_str}_001", "date": today}],
             "seen_jobs": {}}
        bid = search_state.new_batch_id(h)
        assert bid == f"{today_str}_002"


# ── TestPruneSeenJobs ───────────────────────────────────────────────────────────

class TestPruneSeenJobs:
    def test_removes_entries_older_than_30_days(self):
        h = {
            "seen_jobs": {
                "old": {"last_seen": _days_ago(31)},
            }
        }
        search_state._prune_seen_jobs(h)
        assert "old" not in h["seen_jobs"]

    def test_keeps_recent_entries(self):
        h = {
            "seen_jobs": {
                "recent": {"last_seen": _days_ago(10)},
            }
        }
        search_state._prune_seen_jobs(h)
        assert "recent" in h["seen_jobs"]

    def test_missing_date_field_kept(self):
        """Entries with no last_seen or first_seen should not crash and be kept."""
        h = {
            "seen_jobs": {
                "nodate": {},
            }
        }
        search_state._prune_seen_jobs(h)
        assert "nodate" in h["seen_jobs"]
