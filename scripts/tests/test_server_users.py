"""
Unit tests for server_users.py — group-update and preferences endpoints.

Uses the patch_paths fixture from conftest.py which redirects server_jobs.USERS_DIR
to a temp directory. Since server_users delegates all config I/O to server_jobs
(_sj.*), patching server_jobs.USERS_DIR is sufficient.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import server_jobs   # noqa: E402
import server_users  # noqa: E402


# ── Mock HTTP handler ─────────────────────────────────────────────────────────

class _H:
    """Minimal mock of the HTTP request handler used by server_users routes."""
    def __init__(self, body=None):
        self._body = body or {}
        self.sent_body   = None
        self.sent_status = 200

    def _read_json_body(self):
        return dict(self._body)

    def _send(self, raw, content_type='application/json', status=200):
        self.sent_body   = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        self.sent_status = status


# ── TestGroupUpdate ───────────────────────────────────────────────────────────

class TestGroupUpdate:

    def test_updates_existing_group(self, patch_paths):
        uid, ud = patch_paths
        h = _H({'group': {
            'group_id':    'group-test',
            'group_label': 'Updated Label',
            'cv_file':     'new.pdf',
            'primary_keywords': {'en': ['New Role']},
        }})
        result = server_users.handle_post('/api/group-update', {}, uid, h)
        assert result is True
        assert h.sent_status == 200
        assert h.sent_body == {'ok': True, 'group_id': 'group-test'}
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        g = next(g for g in cfg['job_search']['keyword_groups']
                 if g['group_id'] == 'group-test')
        assert g['group_label'] == 'Updated Label'
        assert g['cv_file'] == 'new.pdf'

    def test_missing_group_id_returns_400(self, patch_paths):
        uid, _ = patch_paths
        h = _H({'group': {'group_label': 'No ID'}})
        server_users.handle_post('/api/group-update', {}, uid, h)
        assert h.sent_status == 400
        assert 'error' in h.sent_body

    def test_empty_group_id_returns_400(self, patch_paths):
        uid, _ = patch_paths
        h = _H({'group': {'group_id': '', 'group_label': 'Empty'}})
        server_users.handle_post('/api/group-update', {}, uid, h)
        assert h.sent_status == 400

    def test_nonexistent_group_returns_404(self, patch_paths):
        uid, _ = patch_paths
        h = _H({'group': {'group_id': 'group-does-not-exist'}})
        server_users.handle_post('/api/group-update', {}, uid, h)
        assert h.sent_status == 404

    def test_merge_preserves_unlisted_fields(self, patch_paths):
        uid, ud = patch_paths
        # Seed config with an extra field on the existing group
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        cfg['job_search']['keyword_groups'][0]['_auto_generated'] = True
        (ud / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')

        h = _H({'group': {
            'group_id':    'group-test',
            'group_label': 'Merged',
            'cv_file':     'cv.pdf',
            'primary_keywords': {'en': ['Role']},
        }})
        server_users.handle_post('/api/group-update', {}, uid, h)
        assert h.sent_status == 200
        cfg2 = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        g = cfg2['job_search']['keyword_groups'][0]
        assert g['_auto_generated'] is True   # preserved by {**old, **new} merge
        assert g['group_label'] == 'Merged'   # updated

    def test_unrelated_path_not_handled(self, patch_paths):
        uid, _ = patch_paths
        h = _H()
        result = server_users.handle_post('/api/other-path', {}, uid, h)
        assert result is False


# ── TestPreferencesGet ────────────────────────────────────────────────────────

class TestPreferencesGet:

    def test_returns_safe_defaults_when_key_missing(self, patch_paths):
        uid, _ = patch_paths
        h = _H()
        result = server_users.handle_get('/api/preferences', {}, uid, h)
        assert result is True
        assert h.sent_status == 200
        p = h.sent_body
        assert isinstance(p['preferred_locations'],   list)
        assert isinstance(p['preferred_work_mode'],   list)
        assert isinstance(p['language_skills'],       list)
        assert isinstance(p['preferred_level'],       str)
        assert isinstance(p['date_range_days'],       int)
        assert isinstance(p['max_display'],           int)
        assert isinstance(p['stepstone_enabled'],     bool)
        assert isinstance(p['auto_default_answers'],  bool)

    def test_returns_existing_preferences(self, patch_paths):
        uid, ud = patch_paths
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        cfg['preferences'] = {
            'preferred_locations':            ['Berlin', 'Remote'],
            'language_skills':                ['japanese'],
            'salary_expectation_eur_monthly': 4000,
            'preferred_level':                'senior, lead',
        }
        (ud / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')

        h = _H()
        server_users.handle_get('/api/preferences', {}, uid, h)
        p = h.sent_body
        assert p['preferred_locations'] == ['Berlin', 'Remote']
        assert p['language_skills'] == ['japanese']
        assert p['salary_expectation_eur_monthly'] == 4000
        assert p['preferred_level'] == 'senior, lead'

    def test_returns_stepstone_enabled_from_config(self, patch_paths):
        uid, ud = patch_paths
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        cfg['stepstone'] = {'enabled': True}
        (ud / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')

        h = _H()
        server_users.handle_get('/api/preferences', {}, uid, h)
        assert h.sent_body['stepstone_enabled'] is True

    def test_returns_job_search_fields(self, patch_paths):
        uid, ud = patch_paths
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        cfg['job_search']['date_range_days'] = 7
        cfg['job_search']['max_display']     = 50
        (ud / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')

        h = _H()
        server_users.handle_get('/api/preferences', {}, uid, h)
        assert h.sent_body['date_range_days'] == 7
        assert h.sent_body['max_display']     == 50

    def test_unrelated_path_not_handled(self, patch_paths):
        uid, _ = patch_paths
        result = server_users.handle_get('/api/other-path', {}, uid, _H())
        assert result is False


# ── TestPreferencesPost ───────────────────────────────────────────────────────

class TestPreferencesPost:

    def test_saves_preferred_locations(self, patch_paths):
        uid, ud = patch_paths
        h = _H({'preferred_locations': ['Hamburg', 'Munich']})
        server_users.handle_post('/api/preferences', {}, uid, h)
        assert h.sent_status == 200
        assert h.sent_body == {'ok': True}
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        assert cfg['preferences']['preferred_locations'] == ['Hamburg', 'Munich']

    def test_saves_language_skills(self, patch_paths):
        uid, ud = patch_paths
        h = _H({'language_skills': ['chinese', 'spanish']})
        server_users.handle_post('/api/preferences', {}, uid, h)
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        assert cfg['preferences']['language_skills'] == ['chinese', 'spanish']

    def test_saves_preferred_level_string(self, patch_paths):
        uid, ud = patch_paths
        h = _H({'preferred_level': 'entry, junior, senior'})
        server_users.handle_post('/api/preferences', {}, uid, h)
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        assert cfg['preferences']['preferred_level'] == 'entry, junior, senior'

    def test_saves_stepstone_enabled(self, patch_paths):
        uid, ud = patch_paths
        h = _H({'stepstone_enabled': True})
        server_users.handle_post('/api/preferences', {}, uid, h)
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        assert cfg['stepstone']['enabled'] is True

    def test_saves_auto_default_answers(self, patch_paths):
        uid, ud = patch_paths
        h = _H({'auto_default_answers': False})
        server_users.handle_post('/api/preferences', {}, uid, h)
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        assert cfg['auto_default_answers'] is False

    def test_saves_date_range_and_max_display(self, patch_paths):
        uid, ud = patch_paths
        h = _H({'date_range_days': 7, 'max_display': 50})
        server_users.handle_post('/api/preferences', {}, uid, h)
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        assert cfg['job_search']['date_range_days'] == 7
        assert cfg['job_search']['max_display']     == 50

    def test_partial_update_preserves_other_fields(self, patch_paths):
        uid, ud = patch_paths
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        cfg['preferences'] = {
            'preferred_locations': ['Berlin'],
            'language_skills':     ['japanese'],
        }
        (ud / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')

        h = _H({'language_skills': ['chinese']})
        server_users.handle_post('/api/preferences', {}, uid, h)
        cfg2 = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        assert cfg2['preferences']['preferred_locations'] == ['Berlin']  # unchanged
        assert cfg2['preferences']['language_skills']     == ['chinese'] # updated

    def test_work_mode_saved(self, patch_paths):
        uid, ud = patch_paths
        h = _H({'preferred_work_mode': ['hybrid', 'remote']})
        server_users.handle_post('/api/preferences', {}, uid, h)
        cfg = json.loads((ud / 'config.json').read_text(encoding='utf-8'))
        assert cfg['preferences']['preferred_work_mode'] == ['hybrid', 'remote']
