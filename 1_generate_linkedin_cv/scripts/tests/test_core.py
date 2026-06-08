"""
Unit tests for three core functions in server.py:
  - _update_jd_field()
  - compute_search_analysis()
  - parse_jobs()

All tests use the `patch_paths` fixture (conftest.py) which redirects
server.USERS_DIR to a temporary directory so no real user data is touched.
"""
import json
from pathlib import Path

import pytest

# server is imported at conftest load time (with stdout restored) — just reference it
import server  # noqa: F401 (conftest already patched sys.stdout; this is a safe re-import)

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
