"""Shared fixtures for server.py unit tests."""
import json
import sys
from pathlib import Path

import pytest

# Allow `import server` from the scripts/ parent directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# server.py wraps sys.stdout/stderr with io.TextIOWrapper at import time.
# The wrapper takes ownership of the underlying buffer; when it's GC'd it would
# close pytest's capture buffer.  We detach the buffer before restoring, so the
# TextIOWrapper can be discarded without closing anything.
_saved_stdout = sys.stdout
_saved_stderr = sys.stderr
import server  # noqa: E402 — must follow the sys.path insert above
if sys.stdout is not _saved_stdout:
    try:
        sys.stdout.detach()
    except Exception:
        pass
if sys.stderr is not _saved_stderr:
    try:
        sys.stderr.detach()
    except Exception:
        pass
sys.stdout = _saved_stdout
sys.stderr = _saved_stderr


@pytest.fixture
def uid():
    return 'testuser'


@pytest.fixture
def patch_paths(monkeypatch, tmp_path, uid):
    """
    Redirect server.USERS_DIR to a temp directory and create a minimal user workspace.

    Returns (uid, user_path) where user_path = tmp_path/users/{uid}.
    All server path helpers (_user_dir, get_output_dir, get_config_path, …) resolve
    correctly via the monkeypatched USERS_DIR.
    """
    users_dir = tmp_path / 'users'
    user_path = users_dir / uid
    (user_path / 'output').mkdir(parents=True)
    (user_path / 'my_cv').mkdir()

    (user_path / 'config.json').write_text(json.dumps({
        "job_search": {
            "keyword_groups": [{
                "group_id":    "group-test",
                "group_label": "Test Group",
                "cv_file":     "my_cv.pdf",
                "primary_keywords": {"en": ["Test Role"], "de": []},
                "job_family":       {"en": [],            "de": []},
            }]
        },
        "skill_taxonomy": {},
    }), encoding='utf-8')

    monkeypatch.setattr(server, 'USERS_DIR', users_dir)

    # Reset job cache between tests
    server._jobs_cache.clear()
    server._jobs_cache_mtime.clear()

    return uid, user_path
