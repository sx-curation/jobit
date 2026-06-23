"""
Unit tests for three core functions in server.py:
  - _update_jd_field()
  - compute_search_analysis()
  - parse_jobs()

All tests use the `patch_paths` fixture (conftest.py) which redirects
server.USERS_DIR to a temporary directory so no real user data is touched.
"""
import json
import sys
import types
from pathlib import Path

import pytest

# server is imported at conftest load time (with stdout restored) — just reference it
import server  # noqa: F401 (conftest already patched sys.stdout; this is a safe re-import)
import server_jobs  # noqa: E402

# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_jd(output_dir: Path, rel_path: str, data: dict) -> Path:
    """Create a jd_analysis.json at output_dir/rel_path, making parent dirs."""
    f = output_dir / rel_path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data), encoding='utf-8')
    return f


def _job_summary_row(
    row='1',
    score='85',
    jd_rel='group-test_Corp_Role_20260101/jd_analysis.json',
    group='group-test',
    source='LinkedIn',
    company='Corp',
    title='Role',
    size='S',
    url='https://example.com',
    emphasis='emph',
    missing='miss',
    analyzed='Jan 01',
    last_seen='Jan 05',
):
    """Return a markdown table row string for job_summary.md."""
    score_cell = f'[**{score}**]({jd_rel})' if jd_rel else score
    return (
        f'| {row} | {score_cell} | {group} | {source} | {company} | '
        f'{title} | {size} | [Link]({url}) | {emphasis} | {missing} | '
        f'{analyzed} | {last_seen} |'
    )


_SUMMARY_HEADER = (
    '| # | Score | Group | Source | Company | Title | Size | URL | '
    'Emphasis | Missing | Analyzed | Last |\n'
    '|---|-------|-------|--------|---------|-------|------|-----|'
    '----------|---------|----------|------|\n'
)


# ── _update_jd_field ──────────────────────────────────────────────────────────

class TestUpdateJdField:

    def test_returns_400_when_jd_path_empty(self, patch_paths):
        uid, _ = patch_paths
        resp, status = server._update_jd_field('', 'application_record', 'applied', uid)
        assert status == 400
        assert 'error' in resp

    def test_returns_404_when_file_missing(self, patch_paths):
        uid, _ = patch_paths
        resp, status = server._update_jd_field(
            'no_such_dir/jd_analysis.json', 'application_record', 'applied', uid
        )
        assert status == 404
        assert 'error' in resp

    def test_overwrites_existing_field(self, patch_paths):
        uid, ud = patch_paths
        rel = 'group-test_Corp_Role_20260101/jd_analysis.json'
        jd  = _write_jd(ud / 'output', rel, {'job_id': '1', 'application_record': 'saved'})

        resp, status = server._update_jd_field(rel, 'application_record', 'applied', uid)

        assert status == 200
        assert resp == {'ok': True}
        assert json.loads(jd.read_text())['application_record'] == 'applied'

    def test_adds_new_field(self, patch_paths):
        uid, ud = patch_paths
        rel = 'group-test_Corp_Role_20260101/jd_analysis.json'
        jd  = _write_jd(ud / 'output', rel, {'job_id': '1'})

        _, status = server._update_jd_field(rel, 'user_note', 'interesting role', uid)

        assert status == 200
        assert json.loads(jd.read_text())['user_note'] == 'interesting role'

    def test_writes_valid_json_with_unicode(self, patch_paths):
        uid, ud = patch_paths
        rel = 'group-test_Corp_Role_20260101/jd_analysis.json'
        jd  = _write_jd(ud / 'output', rel, {'job_id': '1'})

        server._update_jd_field(rel, 'user_note', 'note with umlauts: äöüß', uid)

        data = json.loads(jd.read_text(encoding='utf-8'))
        assert data['user_note'] == 'note with umlauts: äöüß'


# ── compute_search_analysis ───────────────────────────────────────────────────

class TestComputeSearchAnalysis:

    def _write_history(self, output_dir: Path, history: dict):
        (output_dir / 'search_history.json').write_text(
            json.dumps(history), encoding='utf-8'
        )

    def test_no_history_file(self, patch_paths):
        uid, _ = patch_paths
        result = server.compute_search_analysis(uid)
        assert result == {'error': 'no search history', 'groups': []}

    def test_invalid_json(self, patch_paths):
        uid, ud = patch_paths
        (ud / 'output' / 'search_history.json').write_text('not json', encoding='utf-8')
        result = server.compute_search_analysis(uid)
        assert 'error' in result
        assert result['groups'] == []

    def test_empty_batches(self, patch_paths):
        uid, ud = patch_paths
        self._write_history(ud / 'output', {'batches': [], 'seen_jobs': {}})
        result = server.compute_search_analysis(uid)
        assert result == {'error': 'no batches', 'groups': []}

    def test_aggregates_keyword_counts_across_batches(self, patch_paths):
        uid, ud = patch_paths
        history = {
            'batches': [
                {'date': '2026-01-01', 'fetched_per_keyword': {'Test Role': 3}},
                {'date': '2026-01-02', 'fetched_per_keyword': {'Test Role': 4}},
            ],
            'seen_jobs': {
                'j1': {'keyword': 'Test Role', 'source': 'linkedin'},
                'j2': {'keyword': 'Test Role', 'source': 'linkedin'},
                'j3': {'keyword': 'Test Role', 'source': 'linkedin'},
            },
        }
        self._write_history(ud / 'output', history)
        result = server.compute_search_analysis(uid)

        assert result['total_batches'] == 2
        kws = result['groups'][0]['keywords']
        assert len(kws) == 1
        assert kws[0]['keyword'] == 'Test Role'
        assert kws[0]['count'] == 3  # 3 entries in seen_jobs

    def test_semicolon_keyword_classified_as_batch(self, patch_paths):
        uid, ud = patch_paths
        # 'Test Role;Other Role' is a Stepstone batch keyword
        history = {
            'batches': [{'date': '2026-01-01',
                         'fetched_per_keyword': {'Test Role;Other Role': 2}}],
            'seen_jobs': {},
        }
        self._write_history(ud / 'output', history)
        result = server.compute_search_analysis(uid)

        assert result['total_batches'] == 1
        # The keyword maps to group '' (first part 'Test Role' is primary → maps to group-test,
        # but Stepstone batch keywords resolve via kw_type_map on the first part)
        # Verify no crash and valid structure returned
        assert 'groups' in result

    def test_score_bands(self, patch_paths):
        uid, ud = patch_paths
        output_dir = ud / 'output'
        # Three analyzed jobs: scores 90 (high), 60 (good), 40 (moderate)
        for jid, score in [('j1', 90), ('j2', 60), ('j3', 40)]:
            _write_jd(output_dir, f'group-test_Corp{jid}_Role_20260101/jd_analysis.json',
                      {'job_id': jid, 'match_score': score})

        history = {
            'batches': [{'date': '2026-01-01', 'fetched_per_keyword': {'Test Role': 3}}],
            'seen_jobs': {
                'j1': {'keyword': 'Test Role', 'source': 'linkedin'},
                'j2': {'keyword': 'Test Role', 'source': 'linkedin'},
                'j3': {'keyword': 'Test Role', 'source': 'linkedin'},
            },
        }
        self._write_history(output_dir, history)
        result = server.compute_search_analysis(uid)

        kw = result['groups'][0]['keywords'][0]
        assert kw['high']     == 1  # 90 >= 70
        assert kw['good']     == 1  # 60 in [50, 70)
        assert kw['moderate'] == 1  # 40 in [30, 50)


# ── parse_jobs ────────────────────────────────────────────────────────────────

class TestParseJobs:

    def _write_summary(self, output_dir: Path, rows: list[str]):
        content = _SUMMARY_HEADER + '\n'.join(rows) + '\n'
        (output_dir / 'job_summary.md').write_text(content, encoding='utf-8')

    def test_returns_empty_when_no_summary(self, patch_paths):
        uid, _ = patch_paths
        assert server.parse_jobs(uid) == []

    def test_parses_basic_row(self, patch_paths):
        uid, ud = patch_paths
        self._write_summary(ud / 'output', [_job_summary_row()])
        jobs = server.parse_jobs(uid)
        assert len(jobs) == 1
        j = jobs[0]
        assert j['score']   == 85.0
        assert j['company'] == 'Corp'
        assert j['title']   == 'Role'
        assert j['source']  == 'LinkedIn'
        assert j['group']   == 'group-test'
        assert j['group_label'] == 'Test Group'
        assert j['url']     == 'https://example.com'

    def test_skips_rows_with_too_few_cells(self, patch_paths):
        uid, ud = patch_paths
        # 7 cells — below the minimum of 8
        short_row = '| 1 | 85 | group-test | LinkedIn | Corp | Role | S |'
        self._write_summary(ud / 'output', [short_row])
        jobs = server.parse_jobs(uid)
        # Only unanalyzed raw entries could still be loaded, but there are none here
        analyzed = [j for j in jobs if j.get('remark') != 'unanalyzed']
        assert analyzed == []

    def test_merges_jd_analysis_data(self, patch_paths):
        uid, ud = patch_paths
        rel = 'group-test_Corp_Role_20260101/jd_analysis.json'
        _write_jd(ud / 'output', rel, {
            'application_record': 'applied',
            'matched_skills':     ['Python'],
            'missing_skills':     ['Go'],
            'user_note':          'great fit',
            'company_info':       {'size': 'Large', 'location': 'Berlin'},
        })
        self._write_summary(ud / 'output', [_job_summary_row(jd_rel=rel)])
        jobs = server.parse_jobs(uid)

        assert len(jobs) >= 1
        j = next(j for j in jobs if j['company'] == 'Corp')
        assert j['application_record'] == 'applied'
        assert j['matched_skills']     == ['Python']
        assert j['missing_skills']     == [{'skill': 'Go', 'severity': 'unknown'}]
        assert j['user_note']          == 'great fit'
        assert j['size']               == 'Large'
        assert j['location']           == 'Berlin'

    def test_materials_ready_flag(self, patch_paths):
        uid, ud = patch_paths
        rel      = 'group-test_Corp_Role_20260101/jd_analysis.json'
        job_dir  = ud / 'output' / 'group-test_Corp_Role_20260101'
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / 'jd_analysis.json').write_text('{}', encoding='utf-8')
        (job_dir / 'cv_final.pdf').write_bytes(b'%PDF')

        self._write_summary(ud / 'output', [_job_summary_row(jd_rel=rel)])
        jobs = server.parse_jobs(uid)

        j = next(j for j in jobs if j['company'] == 'Corp')
        assert j['materials_ready'] is True

    def test_cache_is_populated_after_first_call(self, patch_paths):
        uid, ud = patch_paths
        self._write_summary(ud / 'output', [_job_summary_row()])
        jobs = server.parse_jobs(uid)
        assert len(jobs) >= 1
        assert uid in server._jobs_cache
        assert server._jobs_cache[uid] is not None

    def test_cross_source_remark(self, patch_paths):
        """Same company+title from LinkedIn (analyzed) and Stepstone (analyzed) → remark=multiple source."""
        uid, ud = patch_paths
        # Two rows: same company+title, different sources
        li_row  = _job_summary_row(row='1', jd_rel='group-test_Corp_Role_20260101/jd_analysis.json',
                                   source='LinkedIn', company='DupCorp', title='DupRole')
        st_row  = _job_summary_row(row='2', jd_rel=None, score='72',
                                   source='Stepstone', company='DupCorp', title='DupRole')
        self._write_summary(ud / 'output', [li_row, st_row])
        jobs = server.parse_jobs(uid)

        dup_jobs = [j for j in jobs if j['company'] == 'DupCorp']
        assert len(dup_jobs) == 2
        assert all(j['remark'] == 'multiple source' for j in dup_jobs)


# ── TestParseRelativeDate ─────────────────────────────────────────────────────

class TestParseRelativeDate:
    def test_days_ago(self):
        assert server._parse_relative_date('3 days ago') == 3

    def test_weeks_ago(self):
        assert server._parse_relative_date('2 weeks ago') == 14

    def test_hours_ago(self):
        assert server._parse_relative_date('5 hours ago') == 0

    def test_months_ago(self):
        assert server._parse_relative_date('1 month ago') == 30

    def test_returns_none_on_unrecognized(self):
        assert server._parse_relative_date('recently') is None
        assert server._parse_relative_date('') is None


# ── TestInferLocation ─────────────────────────────────────────────────────────

class TestInferLocation:
    def test_location_from_stepstone_url(self):
        job = {'url': 'https://www.stepstone.de/en/stellenangebote--Senior-Dev--Berlin--123.html', 'location': ''}
        assert server.infer_location(job) == 'Berlin'

    def test_fallback_to_location_field(self):
        job = {'url': 'https://linkedin.com/jobs/view/123', 'location': 'Frankfurt'}
        assert server.infer_location(job) == 'Frankfurt'

    def test_returns_empty_on_missing(self):
        job = {'url': '', 'location': ''}
        assert server.infer_location(job) == ''

    def test_umlaut_slug_mapped(self):
        job = {'url': 'https://www.stepstone.de/en/stellenangebote--Data-Analyst--Muenchen--456.html', 'location': ''}
        assert server.infer_location(job) == 'München'


# ── TestToStrList ─────────────────────────────────────────────────────────────

class TestToStrList:
    def test_none_input(self):
        assert server._to_str_list(None) == []

    def test_string_list(self):
        assert server._to_str_list(['Python', 'SQL']) == ['Python', 'SQL']

    def test_dict_list_with_skill_key(self):
        result = server._to_str_list([{'skill': 'Kubernetes'}])
        assert result == ['Kubernetes']

    def test_dict_list_with_responsibility_key(self):
        result = server._to_str_list([{'responsibility': 'Lead team'}])
        assert result == ['Lead team']

    def test_mixed_types(self):
        result = server._to_str_list(['Python', {'skill': 'SQL'}, {'gap': 'Spark'}])
        assert result == ['Python', 'SQL', 'Spark']

    def test_filters_empty_strings(self):
        result = server._to_str_list([{'skill': ''}, 'valid'])
        assert result == ['valid']


# ── TestComputeGroupStats ─────────────────────────────────────────────────────

class TestComputeGroupStats:
    """Baseline tests for compute_group_stats() — established before server.py split."""

    def _write_jd_analysis(self, output_dir: Path, folder: str, data: dict) -> Path:
        d = output_dir / folder
        d.mkdir(parents=True, exist_ok=True)
        p = d / 'jd_analysis.json'
        p.write_text(json.dumps(data), encoding='utf-8')
        return p

    def _write_history(self, output_dir: Path, history: dict):
        (output_dir / 'search_history.json').write_text(
            json.dumps(history), encoding='utf-8'
        )

    def test_returns_one_entry_per_group(self, patch_paths):
        uid, _ = patch_paths
        result = server.compute_group_stats(uid)
        assert len(result) == 1
        assert result[0]['group_id'] == 'group-test'

    def test_empty_output_dir_gives_zero_job_count(self, patch_paths):
        uid, _ = patch_paths
        result = server.compute_group_stats(uid)
        assert result[0]['job_count'] == 0
        assert result[0]['avg_score'] is None

    def test_job_count_and_avg_score(self, patch_paths):
        uid, ud = patch_paths
        out = ud / 'output'
        self._write_jd_analysis(out, 'group-test_A_Dev_20260101', {'match_score': 80})
        self._write_jd_analysis(out, 'group-test_B_Dev_20260101', {'match_score': 60})

        result = server.compute_group_stats(uid)
        g = result[0]
        assert g['job_count'] == 2
        assert g['avg_score'] == 70.0

    def test_top_missing_skills_aggregated(self, patch_paths):
        uid, ud = patch_paths
        out = ud / 'output'
        self._write_jd_analysis(out, 'group-test_A_Dev_20260101',
            {'missing_skills': ['Python', 'SQL']})
        self._write_jd_analysis(out, 'group-test_B_Dev_20260101',
            {'missing_skills': ['Python', 'Tableau']})

        result = server.compute_group_stats(uid)
        skills = {s['skill']: s['count'] for s in result[0]['top_missing_skills']}
        assert skills['Python'] == 2
        assert skills['SQL'] == 1
        assert skills['Tableau'] == 1

    def test_missing_skills_as_dicts(self, patch_paths):
        uid, ud = patch_paths
        out = ud / 'output'
        self._write_jd_analysis(out, 'group-test_A_Dev_20260101',
            {'missing_skills': [{'skill': 'Kubernetes'}, {'skill': 'Terraform'}]})

        result = server.compute_group_stats(uid)
        skills = [s['skill'] for s in result[0]['top_missing_skills']]
        assert 'Kubernetes' in skills
        assert 'Terraform' in skills

    def test_top_matched_skills_aggregated(self, patch_paths):
        uid, ud = patch_paths
        out = ud / 'output'
        self._write_jd_analysis(out, 'group-test_A_Dev_20260101',
            {'matched_skills': ['Python', 'SQL']})
        self._write_jd_analysis(out, 'group-test_B_Dev_20260101',
            {'matched_skills': ['Python']})

        result = server.compute_group_stats(uid)
        skills = {s['skill']: s['count'] for s in result[0]['top_matched_skills']}
        assert skills['Python'] == 2
        assert skills['SQL'] == 1

    def test_is_active_true_for_recent_jd(self, patch_paths):
        uid, ud = patch_paths
        self._write_jd_analysis(ud / 'output', 'group-test_A_Dev_20260101',
            {'match_score': 75})
        result = server.compute_group_stats(uid)
        assert result[0]['is_active'] is True

    def test_search_timeline_from_history(self, patch_paths):
        uid, ud = patch_paths
        out = ud / 'output'
        self._write_history(out, {
            'batches': [
                {
                    'batch_id': '20260101_001',
                    'group_id': 'group-test',
                    'date': '2026-01-01',
                    'new_total': 5,
                    'hidden_low_score': 1,
                    'skipped_duplicate': 1,
                    'fetched_total': 10,
                    'fetched_per_source': {'linkedin': 10},
                }
            ],
            'seen_jobs': {},
        })

        result = server.compute_group_stats(uid)
        timeline = result[0]['search_timeline']
        assert len(timeline) == 1
        assert timeline[0]['date'] == '2026-01-01'
        assert timeline[0]['fetched_total'] == 10
        assert timeline[0]['new_net'] == 3  # 5 - 1 - 1
        assert 'linkedin: 10' in timeline[0]['sources']

    def test_folders_not_in_group_excluded(self, patch_paths):
        uid, ud = patch_paths
        out = ud / 'output'
        self._write_jd_analysis(out, 'group-other_X_Dev_20260101', {'match_score': 90})

        result = server.compute_group_stats(uid)
        assert result[0]['job_count'] == 0  # group-other_ doesn't match group-test_

    def test_corrupted_jd_skipped_gracefully(self, patch_paths):
        uid, ud = patch_paths
        out = ud / 'output'
        d = out / 'group-test_A_Dev_20260101'
        d.mkdir(parents=True, exist_ok=True)
        (d / 'jd_analysis.json').write_text('not valid json', encoding='utf-8')

        result = server.compute_group_stats(uid)
        assert result[0]['job_count'] == 1  # folder found, but score not parsed
        assert result[0]['avg_score'] is None


# ── TestRefreshSummary ────────────────────────────────────────────────────────

class _H:
    """Minimal mock HTTP handler for route handler tests."""
    def __init__(self, body=None):
        self._body = body or {}
        self.sent_body   = None
        self.sent_status = 200

    def _read_json_body(self):
        return dict(self._body)

    def _send(self, raw, content_type='application/json', status=200):
        self.sent_body   = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
        self.sent_status = status


def _fake_gs(records=None, markdown=''):
    """Return a fake generate_summary module."""
    gs = types.ModuleType('generate_summary')
    gs.load_all_analyses  = lambda _: list(records) if records is not None else []
    gs.cross_source_dedup = lambda r: r
    gs.build_markdown     = lambda r: markdown
    return gs


class TestRefreshSummary:

    def test_empty_analyses_returns_ok_zero(self, patch_paths, monkeypatch):
        uid, _ = patch_paths
        monkeypatch.setitem(sys.modules, 'generate_summary', _fake_gs(records=[]))
        h = _H()
        result = server_jobs.handle_post('/api/refresh-summary', {}, uid, h)
        assert result is True
        assert h.sent_status == 200
        assert h.sent_body['ok'] is True
        assert h.sent_body['jobs'] == 0
        assert 'note' in h.sent_body

    def test_returns_job_count(self, patch_paths, monkeypatch):
        uid, _ = patch_paths
        records = [{'job_id': 'j1'}, {'job_id': 'j2'}]
        monkeypatch.setitem(sys.modules, 'generate_summary', _fake_gs(records=records, markdown='md\n'))
        h = _H()
        server_jobs.handle_post('/api/refresh-summary', {}, uid, h)
        assert h.sent_status == 200
        assert h.sent_body['ok'] is True
        assert h.sent_body['jobs'] == 2

    def test_writes_job_summary_md(self, patch_paths, monkeypatch):
        uid, ud = patch_paths
        content = '| some | markdown |\n'
        monkeypatch.setitem(sys.modules, 'generate_summary',
                            _fake_gs(records=[{'job_id': 'j1'}], markdown=content))
        h = _H()
        server_jobs.handle_post('/api/refresh-summary', {}, uid, h)
        summary = ud / 'output' / 'job_summary.md'
        assert summary.exists()
        assert summary.read_text(encoding='utf-8') == content

    def test_invalidates_jobs_cache(self, patch_paths, monkeypatch):
        uid, _ = patch_paths
        server._jobs_cache[uid]       = [{'job_id': 'stale'}]
        server._jobs_cache_mtime[uid] = 0.0
        monkeypatch.setitem(sys.modules, 'generate_summary',
                            _fake_gs(records=[{'job_id': 'j1'}], markdown='x\n'))
        h = _H()
        server_jobs.handle_post('/api/refresh-summary', {}, uid, h)
        assert uid not in server._jobs_cache
        assert uid not in server._jobs_cache_mtime

    def test_unrelated_path_not_handled(self, patch_paths):
        uid, _ = patch_paths
        result = server_jobs.handle_post('/api/other-path', {}, uid, _H())
        assert result is False
