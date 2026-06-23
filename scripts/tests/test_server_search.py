"""
Unit tests for UX-A/B1 additions in server_search.py:
  - _validate_config()
  - /api/health route
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server_search  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_cfg(groups):
    return {"job_search": {"keyword_groups": groups}, "skill_taxonomy": {}}


def _group(gid="group-test", cv_file="cv.pdf", en=None, de=None):
    return {
        "group_id": gid,
        "group_label": gid,
        "cv_file": cv_file,
        "primary_keywords": {"en": en if en is not None else ["analyst"], "de": de or []},
        "job_family": {"en": [], "de": []},
    }


# ── _validate_config ───────────────────────────────────────────────────────────

class TestValidateConfig:

    def test_no_groups_returns_error(self, tmp_path):
        cfg = _make_cfg([])
        uid = "u1"
        (tmp_path / uid / "my_cv").mkdir(parents=True)
        with patch.object(server_search, "_user_dir", return_value=tmp_path / uid):
            errs = server_search._validate_config(cfg, uid)
        assert len(errs) == 1
        assert "keyword_groups" in errs[0]

    def test_missing_cv_file_field(self, tmp_path):
        g = _group(cv_file="")
        cfg = _make_cfg([g])
        uid = "u1"
        (tmp_path / uid / "my_cv").mkdir(parents=True)
        with patch.object(server_search, "_user_dir", return_value=tmp_path / uid):
            errs = server_search._validate_config(cfg, uid)
        assert any("cv_file" in e for e in errs)

    def test_cv_file_not_on_disk(self, tmp_path):
        g = _group(cv_file="missing.pdf")
        cfg = _make_cfg([g])
        uid = "u1"
        (tmp_path / uid / "my_cv").mkdir(parents=True)
        # Do NOT create the file
        with patch.object(server_search, "_user_dir", return_value=tmp_path / uid):
            errs = server_search._validate_config(cfg, uid)
        assert any("missing.pdf" in e for e in errs)

    def test_keywords_both_empty(self, tmp_path):
        g = _group(cv_file="my_cv/cv.pdf", en=[], de=[])
        cfg = _make_cfg([g])
        uid = "u1"
        cv_dir = tmp_path / uid / "my_cv"
        cv_dir.mkdir(parents=True)
        (cv_dir / "cv.pdf").write_bytes(b"%PDF-1")
        with patch.object(server_search, "_user_dir", return_value=tmp_path / uid):
            errs = server_search._validate_config(cfg, uid)
        assert any("primary_keywords" in e for e in errs)

    def test_valid_config_no_errors(self, tmp_path):
        g = _group(cv_file="my_cv/cv.pdf", en=["data analyst"])
        cfg = _make_cfg([g])
        uid = "u1"
        cv_dir = tmp_path / uid / "my_cv"
        cv_dir.mkdir(parents=True)
        (cv_dir / "cv.pdf").write_bytes(b"%PDF-1")
        with patch.object(server_search, "_user_dir", return_value=tmp_path / uid):
            errs = server_search._validate_config(cfg, uid)
        assert errs == []

    def test_multiple_groups_collects_all_errors(self, tmp_path):
        g1 = _group("group-a", cv_file="my_cv/missing_a.pdf", en=["role"])
        g2 = _group("group-b", cv_file="", en=[])
        cfg = _make_cfg([g1, g2])
        uid = "u1"
        (tmp_path / uid / "my_cv").mkdir(parents=True)
        with patch.object(server_search, "_user_dir", return_value=tmp_path / uid):
            errs = server_search._validate_config(cfg, uid)
        assert len(errs) >= 2

    def test_de_keywords_satisfy_requirement(self, tmp_path):
        g = _group(cv_file="my_cv/cv.pdf", en=[], de=["Analyst"])
        cfg = _make_cfg([g])
        uid = "u1"
        cv_dir = tmp_path / uid / "my_cv"
        cv_dir.mkdir(parents=True)
        (cv_dir / "cv.pdf").write_bytes(b"%PDF-1")
        with patch.object(server_search, "_user_dir", return_value=tmp_path / uid):
            errs = server_search._validate_config(cfg, uid)
        assert errs == []


# ── /api/health ────────────────────────────────────────────────────────────────

def _make_handler(sent_data):
    h = MagicMock()
    def _send(body, *a, **kw):
        sent_data.append(json.loads(body))
    h._send.side_effect = _send
    return h


class TestHealthRoute:

    def test_health_returns_true_when_claude_found(self):
        sent = []
        h = _make_handler(sent)
        with patch("server_search.shutil.which", return_value="/usr/bin/claude"):
            handled = server_search.handle_get("/api/health", {}, "u1", h)
        assert handled is True
        assert sent[0]["claude"] is True

    def test_health_returns_false_when_claude_missing(self):
        sent = []
        h = _make_handler(sent)
        with patch("server_search.shutil.which", return_value=None):
            handled = server_search.handle_get("/api/health", {}, "u1", h)
        assert handled is True
        assert sent[0]["claude"] is False

    def test_health_not_claimed_for_other_paths(self):
        h = MagicMock()
        handled = server_search.handle_get("/api/other", {}, "u1", h)
        assert handled is False
        h._send.assert_not_called()


class TestSearchStatus:

    def test_status_returns_searches_list(self):
        sent = []
        h = _make_handler(sent)
        with patch.object(server_search, "get_running_searches", return_value=[]):
            server_search.handle_get("/api/search-status", {}, "u1", h)
        assert sent[0] == {"running": False, "searches": []}

    def test_status_running_true_when_searches_exist(self):
        sent = []
        h = _make_handler(sent)
        fake = [{"key": "u1:group-da", "uid": "u1", "group_id": "group-da"}]
        with patch.object(server_search, "get_running_searches", return_value=fake):
            server_search.handle_get("/api/search-status", {}, "u1", h)
        assert sent[0]["running"] is True
        assert len(sent[0]["searches"]) == 1


class TestConcurrentSearchLimit:

    def _post_search(self, group_id, uid="u1", running=None):
        sent = []
        h = _make_handler(sent)
        h._read_json_body = MagicMock(return_value={"group_id": group_id})
        cfg = _make_cfg([_group(cv_file="my_cv/cv.pdf")])
        with patch.object(server_search, "read_config", return_value=cfg), \
             patch.object(server_search, "get_keyword_groups", return_value=(None, [_group()], None)), \
             patch.object(server_search, "_validate_config", return_value=[]), \
             patch.object(server_search, "get_running_searches", return_value=running or []), \
             patch.object(server_search, "_is_key_running", return_value=False), \
             patch("threading.Thread"):
            server_search.handle_post("/api/search", {}, uid, h)
        return sent, h

    def test_429_when_two_already_running(self):
        # Two searches already running for "group-test" and "group-test2"
        g2 = _group("group-test2", cv_file="my_cv/cv.pdf")
        running = [
            {"key": "u1:group-test",  "uid": "u1", "group_id": "group-test"},
            {"key": "u1:group-test2", "uid": "u1", "group_id": "group-test2"},
        ]
        # Request "group-test3" — valid but over limit
        g3 = _group("group-test3", cv_file="my_cv/cv.pdf")
        cfg = _make_cfg([_group(), g2, g3])
        sent = []
        h = _make_handler(sent)
        h._read_json_body = MagicMock(return_value={"group_id": "group-test3"})
        with patch.object(server_search, "read_config", return_value=cfg), \
             patch.object(server_search, "get_keyword_groups", return_value=(None, [_group(), g2, g3], None)), \
             patch.object(server_search, "_validate_config", return_value=[]), \
             patch.object(server_search, "get_running_searches", return_value=running), \
             patch.object(server_search, "_is_key_running", return_value=False), \
             patch("threading.Thread"):
            server_search.handle_post("/api/search", {}, "u1", h)
        calls = h._send.call_args_list
        statuses = [c.kwargs.get("status") for c in calls]
        assert 429 in statuses

    def test_409_when_same_group_running(self):
        # "group-test" is already running — requesting it again should 409
        running = [{"key": "u1:group-test", "uid": "u1", "group_id": "group-test"}]
        cfg = _make_cfg([_group(cv_file="my_cv/cv.pdf")])
        sent = []
        h = _make_handler(sent)
        h._read_json_body = MagicMock(return_value={"group_id": "group-test"})
        with patch.object(server_search, "read_config", return_value=cfg), \
             patch.object(server_search, "get_keyword_groups", return_value=(None, [_group()], None)), \
             patch.object(server_search, "_validate_config", return_value=[]), \
             patch.object(server_search, "get_running_searches", return_value=running), \
             patch.object(server_search, "_is_key_running", return_value=True), \
             patch("threading.Thread"):
            server_search.handle_post("/api/search", {}, "u1", h)
        calls = h._send.call_args_list
        statuses = [c.kwargs.get("status") for c in calls]
        assert 409 in statuses
