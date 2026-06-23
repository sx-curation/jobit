#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server_jobs.py — Job data logic extracted from server.py (Week 3 partial split).

Contains: job parsing/caching, config helpers, group stats, search analysis,
          skill-gap aggregation, and the JD field-update helper.

server.py imports everything from here and re-exports it so callers remain stable.
"""
import json
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── Paths (must match server.py) ───────────────────────────────────────────────
PROJECT_DIR = Path(__file__).resolve().parent.parent
USERS_DIR   = PROJECT_DIR / 'users'
USERS_JSON  = PROJECT_DIR / 'users.json'

# ── Locks / cache ─────────────────────────────────────────────────────────────
_write_lock       = threading.Lock()
_jobs_cache: dict       = {}
_jobs_cache_mtime: dict = {}
_jobs_cache_lock  = threading.Lock()

# ── Path helpers ───────────────────────────────────────────────────────────────
def _user_dir(uid: str) -> Path:      return USERS_DIR / uid
def get_output_dir(uid: str) -> Path: return _user_dir(uid) / 'output'
def get_cv_dir(uid: str)     -> Path: return _user_dir(uid) / 'my_cv'
def get_config_path(uid: str)-> Path: return _user_dir(uid) / 'config.json'
def get_job_summary(uid: str)-> Path: return get_output_dir(uid) / 'job_summary.md'

# ── Location inference from Stepstone URL ─────────────────────────────────────
_CITY_SLUG_MAP = {
    "Hamburg": "Hamburg", "Berlin": "Berlin", "Munich": "Munich",
    "Frankfurt": "Frankfurt", "Lueneburg": "Lüneburg", "Duesseldorf": "Düsseldorf",
    "Essen": "Essen", "Koeln": "Köln", "Muenchen": "München", "Karben": "Karben",
    "Nuernberg": "Nürnberg", "Stuttgart": "Stuttgart", "Cologne": "Köln",
}

def infer_location(job: dict) -> str:
    '''Infer city display name from Stepstone URL slug; fallback to location field.'''
    url = job.get('url', '') or ''
    if 'stepstone.de' in url:
        for slug, display in _CITY_SLUG_MAP.items():
            if f'-{slug}-' in url:
                return display
    return job.get('location', '') or ''

# ── Utility functions ──────────────────────────────────────────────────────────
def _to_str_list(items) -> list:
    """Return string list from either plain strings or object-format items."""
    result = []
    for item in (items or []):
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            result.append(
                item.get('responsibility') or item.get('skill') or item.get('gap') or ''
            )
    return [s for s in result if s]


_RELATIVE_DATE_RE = re.compile(
    r'(\d+)\s+(hour|day|week|month)s?\s+ago', re.IGNORECASE
)

def _parse_relative_date(s: str):
    """Parse LinkedIn-style relative dates like '2 days ago' → int days. Returns None if unrecognised."""
    m = _RELATIVE_DATE_RE.search(s)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    return {'hour': 0, 'day': n, 'week': n * 7, 'month': n * 30}[unit]


_LEVEL_RULES = [
    ('director',    ['director', 'vp ', ' vp', 'chief ', 'c-level']),
    ('manager',     ['manager', 'head of']),
    ('lead/senior', ['senior', 'lead']),
    ('entry/junior',['junior', 'intern', 'trainee', 'werkstudent', 'entry']),
    ('associate',   ['associate', 'assistant manager']),
]

def _get_job_level(title: str) -> str:
    t = (title or '').lower()
    for level, kws in _LEVEL_RULES:
        if any(kw in t for kw in kws):
            return level
    return 'unknown'

# ── Config helpers ─────────────────────────────────────────────────────────────
def read_config(uid: str):
    return json.loads(get_config_path(uid).read_text(encoding='utf-8'))

def _load_taxonomy(uid: str) -> dict:
    """Merge global_taxonomy.json (base) with user config skill_taxonomy (append)."""
    global_path = PROJECT_DIR / 'config' / 'global_taxonomy.json'
    try:
        global_tax = json.loads(global_path.read_text(encoding='utf-8'))
    except Exception:
        global_tax = {}
    try:
        user_tax = read_config(uid).get('skill_taxonomy', {})
    except Exception:
        user_tax = {}
    merged: dict = {}
    for cat in set(list(global_tax.keys()) + list(user_tax.keys())):
        seen: set = set()
        merged_cat: list = []
        for item in global_tax.get(cat, []) + user_tax.get(cat, []):
            if item not in seen:
                seen.add(item)
                merged_cat.append(item)
        merged[cat] = merged_cat
    return merged

def write_config(data, uid: str):
    with _write_lock:
        get_config_path(uid).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
        )

def _set_nested(obj, path_keys, value):
    for k in path_keys[:-1]:
        obj = obj[k]
    obj[path_keys[-1]] = value

def get_keyword_groups(data=None, uid: str = None):
    '''Return keyword_groups list from config regardless of nesting.'''
    if data is None:
        uid = uid or ''
        data = read_config(uid)
    cfg = data
    if 'keyword_groups' in cfg:
        return cfg, cfg['keyword_groups'], ['keyword_groups']
    js = cfg.get('job_search', {})
    if 'keyword_groups' in js:
        return cfg, js['keyword_groups'], ['job_search', 'keyword_groups']
    return cfg, [], []

# ── Parse + merge job data ─────────────────────────────────────────────────────
def parse_jobs(uid: str):
    '''Parse job_summary.md + jd_analysis.json files.
    Returns cached result when job_summary.md mtime is unchanged.'''
    job_summary = get_job_summary(uid)
    output_dir  = get_output_dir(uid)

    try:
        mtime = job_summary.stat().st_mtime if job_summary.exists() else 0.0
    except OSError:
        mtime = 0.0

    with _jobs_cache_lock:
        if mtime and mtime == _jobs_cache_mtime.get(uid) and _jobs_cache.get(uid):
            return list(_jobs_cache[uid])

    if not job_summary.exists():
        return []

    jobs = []
    header_done = False

    cfg = read_config(uid)
    _, kgs, _ = get_keyword_groups(cfg, uid)
    group_label_map = {g.get('group_id',''): g.get('group_label', g.get('group_id','')) for g in kgs}

    with open(job_summary, encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        line = line.rstrip()
        if not line.startswith('|'):
            continue
        if re.match(r'\|\s*[-:]+\s*\|', line):
            header_done = True
            continue
        if not header_done:
            continue

        cells = [c.strip() for c in line.split('|')[1:-1]]
        if len(cells) < 8:
            continue

        score_cell = cells[1]
        sm = re.search(r'\*?\*?(\d+(?:\.\d+)?)\*?\*?\]\((.+?jd_analysis\.json)\)', score_cell)
        if sm:
            score_val = float(sm.group(1))
            jd_rel    = sm.group(2)
        else:
            sm2 = re.search(r'(\d+(?:\.\d+)?)', score_cell)
            score_val = float(sm2.group(1)) if sm2 else None
            jd_rel    = None

        url_cell = cells[7] if len(cells) > 7 else ''
        um = re.search(r'\[Link\]\(([^)]+)\)', url_cell)
        url = um.group(1) if um else ''

        emphasis_raw = re.sub(r'\s*\+\d+\s*$', '', cells[8] if len(cells) > 8 else '').strip()
        missing_raw  = re.sub(r'\s*\+\d+\s*$', '', cells[9] if len(cells) > 9 else '').strip()

        group_id = cells[2]
        jobs.append({
            'row':                      cells[0],
            'score':                    score_val,
            'jd_path':                  jd_rel,
            'group':                    group_id,
            'group_label':              group_label_map.get(group_id, group_id),
            'source':                   cells[3],
            'company':                  cells[4],
            'title':                    cells[5],
            'size':                     cells[6] if len(cells) > 6 else '',
            'location':                 '',
            'inferred_location':        '',
            'url':                      url,
            'recommended_emphasis_raw': emphasis_raw,
            'missing_skills_raw':       missing_raw,
            'analyzed':                 cells[10] if len(cells) > 10 else '',
            'last_seen':                cells[11] if len(cells) > 11 else '',
            'remark':                   '',
            'application_record':       None,
            'user_note':                '',
            'materials_ready':          False,
            'core_responsibilities':    [],
            'culture_keywords':         [],
            'matched_skills':           [],
            'missing_skills':           [],
            'bonus_skills':             [],
            'required_skills':          [],
            'recommended_emphasis':     [],
            'decision_score':           -1,
            'decision_signals':         {},
            'decision_notes':           [],
            'job_family_detected':      {},
            'legitimacy_verdict':       'UNKNOWN',
            'legitimacy_score':         -1,
            'legitimacy_flags':         [],
            'legitimacy_repost':        False,
            'legitimacy_hiring':        'unknown',
            'gap_summary':              {},
            'customization_potential':  {},
            'estimated_max_score':      -1,
            'company_profile':          {},
            'kununu_overall':           None,
            'kununu_wlb':               None,
            'salary_range':             None,
            'salary_vs_expect':         'unknown',
            'culture_signals':          {},
            'posted_date':              '',
            'days_since_posted':        None,
            'mentioned_chinese':        None,
            'mentioned_japanese':       None,
            'job_level':                'unknown',
        })

    _sh_path = output_dir / 'search_history.json'
    _seen_jobs: dict = {}
    if _sh_path.exists():
        try:
            _seen_jobs = json.loads(_sh_path.read_text(encoding='utf-8')).get('seen_jobs', {})
        except Exception:
            pass

    for job in jobs:
        if not job['jd_path']:
            continue
        jd_file = output_dir / job['jd_path']
        if not jd_file.exists():
            continue
        try:
            detail = json.loads(jd_file.read_text(encoding='utf-8'))
            raw = detail.get('application_record', None)
            if isinstance(raw, dict):
                job['application_record'] = raw.get('status')
                job['applied_at'] = raw.get('ts')
            else:
                job['application_record'] = raw
                job['applied_at'] = None
            job['core_responsibilities'] = _to_str_list(detail.get('core_responsibilities', []))
            job['culture_keywords']      = detail.get('culture_keywords', [])
            job['matched_skills']        = detail.get('matched_skills') or [
                {'skill': s['skill'], 'evidence': s.get('evidence', '')}
                for s in (detail.get('required_skills') or [])
                if isinstance(s, dict) and (s.get('candidate_has') or s.get('hit'))
            ]
            raw_ms = detail.get('missing_skills') or []
            if not raw_ms:
                _fit = detail.get('fit_summary') or {}
                _rs_missing = [
                    {'skill': s['skill'], 'severity': 'required' if s.get('risk') == 'HIGH' else 'nice_to_have'}
                    for s in (detail.get('required_skills') or [])
                    if isinstance(s, dict) and not (
                        s['candidate_has'] if 'candidate_has' in s else s.get('hit', True)
                    )
                ]
                raw_ms = _rs_missing or [
                    {'skill': g, 'severity': 'nice_to_have'} for g in (_fit.get('gaps') or [])
                ]
            job['missing_skills']        = [
                item if isinstance(item, dict) else {'skill': item, 'severity': 'unknown'}
                for item in raw_ms if item
            ]
            job['bonus_skills']          = detail.get('bonus_skills', [])
            job['required_skills']       = _to_str_list(detail.get('required_skills', []))
            _fit2 = detail.get('fit_summary') or {}
            job['recommended_emphasis']  = (
                detail.get('recommended_emphasis') or
                detail.get('strengths') or
                _fit2.get('strengths') or []
            )
            job['user_note']             = detail.get('user_note', '')
            job['decision_score']        = detail.get('decision_score', -1)
            job['decision_signals']      = detail.get('decision_signals', {})
            job['decision_notes']        = detail.get('decision_notes', [])
            job['job_family_detected']   = detail.get('job_family', {})
            leg = detail.get('legitimacy', {})
            job['legitimacy_verdict']    = leg.get('verdict', 'UNKNOWN')
            job['legitimacy_score']      = leg.get('score', -1)
            job['legitimacy_flags']      = leg.get('red_flags', [])
            job['legitimacy_repost']     = leg.get('repost_info', {}).get('detected', False)
            job['legitimacy_hiring']     = leg.get('hiring_signal', {}).get('verdict', 'unknown')
            job['gap_summary']           = detail.get('gap_summary', {})
            job['customization_potential'] = detail.get('customization_potential', {})
            job['estimated_max_score']   = detail.get('customization_potential', {}).get('estimated_max_score', -1)
            cp = detail.get('company_profile', {})
            job['company_profile']       = cp
            job['kununu_overall']        = (cp.get('kununu') or {}).get('overall')
            job['kununu_wlb']            = (cp.get('kununu') or {}).get('wlb')
            job['salary_range']          = (cp.get('salary_research') or {}).get('estimated_range_eur')
            job['salary_vs_expect']      = (cp.get('salary_research') or {}).get('vs_expectation', 'unknown')
            job['culture_signals']       = cp.get('jd_culture_signals', {})
            ci = detail.get('company_info') or {}
            if ci.get('size'):
                job['size'] = ci['size']
            job['location'] = ci.get('location', '')
            job['inferred_location'] = infer_location(job)
            job['job_id'] = str(detail.get('job_id', '') or '')
            raw_pd = detail.get('posted_date') or ''
            if not raw_pd:
                _jid_key = str(detail.get('job_id', '') or '')
                raw_pd = (_seen_jobs.get(_jid_key) or {}).get('first_seen', '')
            job['posted_date'] = raw_pd
            if raw_pd:
                try:
                    posted = datetime.strptime(raw_pd, '%Y-%m-%d').date()
                    job['days_since_posted'] = (datetime.now().date() - posted).days
                except ValueError:
                    job['days_since_posted'] = _parse_relative_date(raw_pd)
            job['mentioned_chinese']  = detail.get('mentioned_chinese')
            job['mentioned_japanese'] = detail.get('mentioned_japanese')
            job['job_level'] = detail.get('job_level') or _get_job_level(job['title'])
        except Exception as e:
            print(f'  WARN {jd_file.name}: {e}', file=sys.stderr)

    for job in jobs:
        if not job['jd_path']:
            continue
        job_dir = output_dir / Path(job['jd_path']).parent
        job['materials_ready'] = (job_dir / 'cv_ats.pdf').exists() or (job_dir / 'cv_final.pdf').exists()


    src_map = defaultdict(set)
    for job in jobs:
        key = (job['company'].strip().lower(), job['title'].strip().lower()[:60])
        src = (job['source'] or '').lower()
        if 'linkedin' in src:
            src_map[key].add('linkedin')
        elif 'stepstone' in src:
            src_map[key].add('stepstone')

    for job in jobs:
        key = (job['company'].strip().lower(), job['title'].strip().lower()[:60])
        if 'linkedin' in src_map[key] and 'stepstone' in src_map[key]:
            job['remark'] = 'multiple source'

    with _jobs_cache_lock:
        _jobs_cache[uid] = jobs
        _jobs_cache_mtime[uid] = mtime

    return jobs


# ── Group stats ────────────────────────────────────────────────────────────────
def _load_search_batches(uid: str):
    '''Return batches list from search_history.json, or [] if missing/invalid.'''
    history_file = get_output_dir(uid) / 'search_history.json'
    if not history_file.exists():
        return []
    try:
        return json.loads(history_file.read_text(encoding='utf-8')).get('batches', [])
    except Exception:
        return []


def compute_group_stats(uid: str):
    cfg, groups, _ = get_keyword_groups(uid=uid)
    output_dir = get_output_dir(uid)
    result = []
    now = time.time()
    all_batches = _load_search_batches(uid)

    for grp in groups:
        gid = grp.get('group_id', '')
        prefix = gid + '_'
        folders = [d for d in output_dir.iterdir()
                   if d.is_dir() and d.name.startswith(prefix)] if output_dir.exists() else []

        scores, missing_all, matched_all, latest_mtime = [], [], [], None
        for folder in folders:
            jd = folder / 'jd_analysis.json'
            if not jd.exists():
                continue
            try:
                detail = json.loads(jd.read_text(encoding='utf-8'))
                sc = detail.get('match_score')
                if sc is not None:
                    scores.append(float(sc))
                raw_ms_agg = detail.get('missing_skills', [])
                missing_all.extend(
                    item['skill'] if isinstance(item, dict) else item
                    for item in raw_ms_agg if item
                )
                raw_match = detail.get('matched_skills', [])
                matched_all.extend(
                    item['skill'] if isinstance(item, dict) else item
                    for item in raw_match if item
                )
                mt = jd.stat().st_mtime
                if latest_mtime is None or mt > latest_mtime:
                    latest_mtime = mt
            except Exception:
                pass

        top_missing = [{'skill': s, 'count': c} for s, c in Counter(missing_all).most_common(15)]
        top_matched = [{'skill': s, 'count': c} for s, c in Counter(matched_all).most_common(6)]
        last_search = (datetime.fromtimestamp(latest_mtime).strftime('%b %d')
                       if latest_mtime else None)
        is_active = bool(latest_mtime and (now - latest_mtime) < 7 * 86400)

        group_batches = sorted(
            [b for b in all_batches if b.get('group_id') == gid],
            key=lambda b: b.get('date', ''), reverse=True
        )
        timeline = []
        for b in group_batches[:3]:
            net = b.get('new_total', 0) - b.get('hidden_low_score', 0) - b.get('skipped_duplicate', 0)
            sources = ', '.join(
                f"{k}: {v}" for k, v in (b.get('fetched_per_source') or {}).items()
            )
            timeline.append({
                'date':          b.get('date', ''),
                'new_net':       net,
                'fetched_total': b.get('fetched_total', 0),
                'sources':       sources,
            })

        result.append({
            'group_id':          gid,
            'group_label':       grp.get('group_label', gid),
            'cv_file':           grp.get('cv_file', ''),
            'primary_keywords':  grp.get('primary_keywords', {}),
            'job_family':        grp.get('job_family', {}),
            'job_count':         len(folders),
            'avg_score':         round(sum(scores) / len(scores), 1) if scores else None,
            'top_missing_skills':  top_missing,
            'top_matched_skills':  top_matched,
            'last_search':       last_search,
            'is_active':         is_active,
            'search_timeline':   timeline,
        })

    return result


def compute_search_analysis(uid: str) -> dict:
    '''Return per-group keyword search analysis aggregated across ALL batches.'''
    output_dir   = get_output_dir(uid)
    history_file = output_dir / 'search_history.json'
    if not history_file.exists():
        return {"error": "no search history", "groups": []}
    try:
        history = json.loads(history_file.read_text(encoding='utf-8'))
    except Exception as e:
        return {"error": str(e), "groups": []}

    batches   = history.get("batches", [])
    seen_jobs = history.get("seen_jobs", {})
    if not batches:
        return {"error": "no batches", "groups": []}

    all_kw_counts: dict[str, int] = {}
    for b in batches:
        for kw, cnt in b.get("fetched_per_keyword", {}).items():
            all_kw_counts[kw] = all_kw_counts.get(kw, 0) + cnt

    groups_with_fallback: set[str] = set()
    for b in batches:
        for gid in b.get("groups_with_fallback", []):
            groups_with_fallback.add(gid)

    exact_scores: dict[str, float] = {}
    for jd_file in output_dir.glob("*/jd_analysis.json"):
        try:
            jd = json.loads(jd_file.read_text(encoding='utf-8'))
            jid = str(jd.get("job_id", ""))
            score = jd.get("match_score")
            if jid and score is not None:
                exact_scores[jid] = float(score)
        except Exception:
            pass

    kw_exact_scores: dict[str, list[float]] = {}
    kw_sources:      dict[str, set[str]]    = {}
    kw_distinct:     dict[str, int]         = {}
    for jid, jinfo in seen_jobs.items():
        kw  = jinfo.get("keyword", "")
        src = jinfo.get("source", "linkedin")
        if not kw:
            continue
        kw_sources.setdefault(kw, set()).add(src)
        kw_distinct[kw] = kw_distinct.get(kw, 0) + 1
        if jid in exact_scores:
            kw_exact_scores.setdefault(kw, []).append(exact_scores[jid])

    cfg, groups_cfg, _ = get_keyword_groups(uid=uid)
    kw_type_map: dict[str, tuple] = {}
    for g in groups_cfg:
        gid = g.get("group_id", "")
        for lang in ("en", "de"):
            for kw in g.get("primary_keywords", {}).get(lang, []):
                kw_type_map.setdefault(kw, (gid, "primary"))
            for kw in g.get("job_family", {}).get(lang, []):
                kw_type_map.setdefault(kw, (gid, "fallback"))

    group_kw_data: dict[str, list[dict]] = {g["group_id"]: [] for g in groups_cfg}
    for kw, _fetch_count in all_kw_counts.items():
        if ";" in kw:
            first_kw = kw.split(";")[0].strip()
            gid, _ = kw_type_map.get(first_kw, ("", "primary"))
            ktype = "batch"
            default_src = "stepstone"
        else:
            gid, ktype = kw_type_map.get(kw, ("", "primary"))
            default_src = "linkedin"

        scores_list = kw_exact_scores.get(kw, [])
        sources     = sorted(kw_sources.get(kw, {default_src}))
        distinct    = kw_distinct.get(kw, 0)
        high     = sum(1 for s in scores_list if s >= 70)
        good     = sum(1 for s in scores_list if 45 <= s < 70)
        moderate = sum(1 for s in scores_list if 30 <= s < 45)

        if gid in group_kw_data:
            group_kw_data[gid].append({
                "keyword":   kw,
                "type":      ktype,
                "sources":   sources,
                "count":     distinct,
                "analyzed":  len(scores_list),
                "high":      high,
                "good":      good,
                "moderate":  moderate,
            })

    result_groups = []
    for g in groups_cfg:
        gid  = g.get("group_id", "")
        kws  = sorted(group_kw_data.get(gid, []), key=lambda k: k["count"], reverse=True)
        result_groups.append({
            "group_id":           gid,
            "group_label":        g.get("group_label", gid),
            "fallback_triggered": gid in groups_with_fallback,
            "total_fetched":      sum(k["count"] for k in kws),
            "keywords":           kws,
        })

    return {
        "last_search_date": batches[-1].get("date", "") if batches else "",
        "total_batches":    len(batches),
        "groups":           result_groups,
    }


# ── Language normalization for skill gap analysis ──────────────────────────────
_LANG_CANON: dict[str, str] = {
    'german': 'German', 'deutsch': 'German',
    'english': 'English', 'englisch': 'English',
    'french': 'French', 'français': 'French', 'französisch': 'French',
    'spanish': 'Spanish', 'espanol': 'Spanish', 'español': 'Spanish',
    'mandarin': 'Mandarin', 'chinese': 'Mandarin',
    'italian': 'Italian', 'italiano': 'Italian',
    'dutch': 'Dutch', 'portuguese': 'Portuguese', 'japanese': 'Japanese',
    'korean': 'Korean', 'arabic': 'Arabic', 'hindi': 'Hindi',
    'russian': 'Russian', 'polish': 'Polish', 'swedish': 'Swedish',
    'norwegian': 'Norwegian', 'danish': 'Danish', 'turkish': 'Turkish',
}
_LEVEL_CANON: dict[str, str] = {
    'c2': 'C2', 'c1': 'C1', 'b2': 'B2', 'b1': 'B1', 'a2': 'A2', 'a1': 'A1',
    'native speaker': 'Native', 'muttersprache': 'Native', 'native': 'Native',
    'fließend': 'B1+', 'fluent': 'B1+', 'bilingual': 'B1+',
    'verhandlungssicher': 'C1', 'business fluent': 'C1',
    'business proficient': 'C1',
}


def _lang_key(skill_name: str) -> tuple[str, str] | None:
    """Return (canonical_key, display_label) if skill is a language skill, else None.
    Merges aliases (deutsch→German) and format variants (German C1 / German (C1)).
    """
    sl = skill_name.lower()
    lang = next((v for k, v in _LANG_CANON.items() if k in sl), None)
    if lang is None:
        return None
    # Match longest level phrase first to avoid 'c1' matching inside 'business c1'
    level = next(
        (v for k, v in sorted(_LEVEL_CANON.items(), key=lambda x: -len(x[0])) if k in sl),
        None,
    )
    level     = level or 'B1+'
    canon_key = f'lang:{lang}:{level}'
    display   = f'{lang} ({level})'
    return canon_key, display


# ── Tool/domain cluster normalization ─────────────────────────────────────────
# Each entry: (canonical_display, [trigger_keywords_lowercase])
# Clusters are checked in order; first match wins.
# Short acronyms (len ≤ 4) use \b word-boundary; longer phrases use substring.
_TOOL_CLUSTERS: list[tuple[str, list[str]]] = [
    ('SAP / ERP',            ['order management software', 'order management system',
                               'order management tool', 'sage erp', 'erp system',
                               'erp module', 'erp platform', 'erp data',
                               'erp integration', 'erp experience', 'erp', 'sap']),
    ('Salesforce / CRM',     ['salesforce', 'supplier management tool',
                               'supplier management system', 'crm system',
                               'crm platform', 'crm tool', 'crm software',
                               'crm management', 'crm administration', 'crm']),
    ('Marketing Automation / hubspot', ['marketing automation', 'hubspot', 'marketo', 'mailchimp']),
    ('Analytics Tools / GA4',      ['google analytics', 'mixpanel', 'amplitude',
                               'firebase analytics', 'mobile analytics', 'ga4']),
    ('A/B Testing',          ['a/b test', 'ab test', 'experimentation framework',
                               'experiment strategy', 'split test']),
    ('SQL',                  ['sql']),
    ('Python / R',           ['python', 'r programming', 'rstudio']),
    ('BI / Reporting',       ['power bi', 'powerbi', 'bi tool', 'bi platform',
                               'bi solution', 'tableau', 'looker studio', 'looker',
                               'google data studio', 'qlik', 'metabase', 'domo']),
    ('Adobe Creative',       ['adobe creative', 'adobe', 'indesign',
                               'photoshop', 'illustrator']),
    ('Paid Media',           ['google ads', 'facebook ads', 'meta ads', 'linkedin ads',
                               'tiktok ads', 'amazon advertising', 'sponsored ads',
                               'amazon seller central', 'amazon vendor central']),
    ('Cloud Platforms',      ['aws', 'amazon web services', 'azure', 'gcp',
                               'google cloud platform']),
    # Others-category clusters
    ('CMS',                  ['content management system', 'cms system', 'cms platform',
                               'cms tool', 'cms proficiency', 'wordpress', 'cms']),
    ('FMCG / Food Industry', ['food & beverage industry', 'food and beverage industry',
                               'fmcg', 'food industry']),
    ('Payments Domain',      ['payments domain', 'payment domain']),
]


def _tool_cluster_key(skill_name: str, category: str) -> tuple[str, str] | None:
    """Return (canonical_key, display) if skill clusters into a known group, else None.
    Applies to Tools and Others categories only.
    """
    if category not in ('Tools', 'Others'):
        return None
    sl = skill_name.lower()
    for display, keywords in _TOOL_CLUSTERS:
        for kw in sorted(keywords, key=len, reverse=True):
            if len(kw) <= 4:
                hit = bool(re.search(r'\b' + re.escape(kw) + r'\b', sl))
            else:
                hit = kw in sl
            if hit:
                return f'cluster:{display}', display
    return None


# ── Group skill gap aggregation ────────────────────────────────────────────────
def compute_group_skill_gaps(uid: str, group_id: str) -> dict:
    output_dir = get_output_dir(uid)
    taxonomy = _load_taxonomy(uid)

    CAT_MAP = [
        ('tools',    'Tools'),
        ('domain',   'Domains'),
        ('langs',    'Language'),
        ('academic', 'Academic'),
        ('cert',     'Others'),
    ]

    def classify(skill_name: str) -> str:
        sn = skill_name.lower()
        for key, label in CAT_MAP:
            if any(kw in sn for kw in taxonomy.get(key, [])):
                return label
        return 'Others'

    SEVERITY_ORDER = ['hard_blocker', 'learnable', 'nice_to_have', 'unknown']

    skill_map: dict = {}
    total_high_match = 0

    for folder in sorted(output_dir.iterdir()):
        if not folder.is_dir() or not folder.name.startswith(group_id + '_'):
            continue
        jda = folder / 'jd_analysis.json'
        if not jda.exists():
            continue
        try:
            data = json.loads(jda.read_text(encoding='utf-8'))
        except Exception:
            continue

        score = data.get('match_score') or (data.get('scoring') or {}).get('match_score')
        if score is None or float(score) < 45:
            continue
        total_high_match += 1

        raw_ms = data.get('missing_skills') or []
        if not raw_ms:
            fit = data.get('fit_summary') or {}
            rs_missing = [
                {'skill': s['skill'], 'severity': 'nice_to_have'}
                for s in (data.get('required_skills') or [])
                if isinstance(s, dict) and not (
                    s['candidate_has'] if 'candidate_has' in s else s.get('hit', True)
                )
            ]
            raw_ms = rs_missing or [
                {'skill': g, 'severity': 'nice_to_have'} for g in (fit.get('gaps') or [])
            ]

        for item in raw_ms:
            if not item:
                continue
            if isinstance(item, str):
                skill_name, severity = item, 'unknown'
            else:
                skill_name = (item.get('skill') or '').strip()
                severity   = (item.get('severity') or 'unknown')
            if not skill_name:
                continue
            lang_info = _lang_key(skill_name)
            category  = classify(skill_name)
            if lang_info:
                key, display = lang_info
            else:
                cluster_info = _tool_cluster_key(skill_name, category)
                if cluster_info:
                    key, display = cluster_info
                else:
                    key, display = skill_name.lower(), skill_name
            if key not in skill_map:
                skill_map[key] = {
                    'skill':    display,
                    'category': category,
                    'jd_count': 0,
                    'severity_counts': {s: 0 for s in SEVERITY_ORDER},
                }
            skill_map[key]['jd_count'] += 1
            sv = severity if severity in SEVERITY_ORDER else 'unknown'
            skill_map[key]['severity_counts'][sv] += 1

    def worst_sev(counts: dict) -> str:
        for s in SEVERITY_ORDER:
            if counts.get(s, 0) > 0:
                return s
        return 'unknown'

    categories: dict = {'Tools': [], 'Domains': [], 'Language': [], 'Academic': [], 'Others': []}
    for entry in skill_map.values():
        ws = worst_sev(entry['severity_counts'])
        entry['worst_severity'] = ws
        entry['worst_count']    = entry['severity_counts'].get(ws, 0)
        categories[entry['category']].append(entry)

    for cat_items in categories.values():
        cat_items.sort(key=lambda x: (SEVERITY_ORDER.index(x['worst_severity']), -x['jd_count']))

    return {
        'group_id':         group_id,
        'total_high_match': total_high_match,
        'min_score':        45,
        'categories':       categories,
    }


# ── JD file helpers ────────────────────────────────────────────────────────────
def _update_jd_field(jd_path: str, field: str, value, uid: str):
    '''Read jd_analysis.json, set one field, write back. Returns (dict, http_status).'''
    if not jd_path:
        return {'error': f'{field} requires jd_path'}, 400
    jd_file = get_output_dir(uid) / jd_path
    if not jd_file.exists():
        return {'error': f'File not found: {jd_path}'}, 404
    with _write_lock:
        detail = json.loads(jd_file.read_text(encoding='utf-8'))
        detail[field] = value
        jd_file.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding='utf-8')
    with _jobs_cache_lock:
        _jobs_cache.pop(uid, None)
        _jobs_cache_mtime.pop(uid, None)
    return {'ok': True}, 200


# ── Route handlers ─────────────────────────────────────────────────────────────
def handle_get(path: str, qs: dict, uid: str, h) -> bool:
    """Handle GET; return True if handled."""
    if path == '/api/jobs':
        try:
            jobs = parse_jobs(uid)
            h._send(json.dumps(jobs, ensure_ascii=False))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/status':
        try:
            js    = get_job_summary(uid)
            mtime = js.stat().st_mtime if js.exists() else 0.0
            h._send(json.dumps({'mtime': mtime}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/group-stats':
        try:
            h._send(json.dumps(compute_group_stats(uid), ensure_ascii=False))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/search-analysis':
        try:
            h._send(json.dumps(compute_search_analysis(uid), ensure_ascii=False))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/cvfiles':
        try:
            cv_dir = get_cv_dir(uid)
            files  = sorted(p.name for p in cv_dir.glob('*.pdf')) if cv_dir.exists() else []
            h._send(json.dumps(files))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/cvfile':
        try:
            name = qs.get('name', [''])[0]
            if not name or '/' in name or '\\' in name or '..' in name:
                h._send(b'Bad request', 'text/plain', 400); return True
            fpath = get_cv_dir(uid) / name
            if not fpath.exists() or not fpath.is_file():
                h._send(b'Not found', 'text/plain', 404); return True
            h._send(fpath.read_bytes(), 'application/pdf')
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/taxonomy':
        try:
            taxonomy = _load_taxonomy(uid)
            h._send(json.dumps(taxonomy, ensure_ascii=False))
        except Exception:
            h._send(json.dumps({}))
        return True

    elif path == '/api/group_skill_gaps':
        try:
            from urllib.parse import parse_qs, urlparse  # noqa: PLC0415
            inner_qs = parse_qs(urlparse(h.path).query)
            group_id = inner_qs.get('group_id', [''])[0].strip()
            if not group_id:
                h._send(json.dumps({'error': 'group_id required'}), status=400); return True
            result = compute_group_skill_gaps(uid, group_id)
            h._send(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    return False


def handle_post(path: str, qs: dict, uid: str, h) -> bool:
    """Handle POST; return True if handled."""
    if path == '/api/record':
        try:
            data       = h._read_json_body()
            record_val = data.get('record')
            if record_val:
                record_val = {'status': record_val, 'ts': datetime.now(timezone.utc).isoformat()}
            result, status = _update_jd_field(data.get('jd_path'), 'application_record', record_val, uid)
            h._send(json.dumps(result), status=status)
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/note':
        try:
            data   = h._read_json_body()
            result, status = _update_jd_field(data.get('jd_path'), 'user_note', data.get('note', ''), uid)
            h._send(json.dumps(result), status=status)
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/refresh-summary':
        try:
            import generate_summary as _gs
            import os
            output_dir = get_output_dir(uid)
            if not output_dir.exists():
                h._send(json.dumps({'error': f'output dir not found: {output_dir}'}), status=404)
                return True
            records = _gs.load_all_analyses(output_dir)
            if not records:
                h._send(json.dumps({'ok': True, 'jobs': 0, 'note': 'no jd_analysis.json found'}))
                return True
            records = _gs.cross_source_dedup(records)
            md = _gs.build_markdown(records)
            out_path = get_job_summary(uid)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = out_path.with_suffix('.tmp')
            tmp.write_text(md, encoding='utf-8')
            os.replace(tmp, out_path)
            # Invalidate jobs cache so next /api/jobs returns fresh data
            with _jobs_cache_lock:
                _jobs_cache.pop(uid, None)
                _jobs_cache_mtime.pop(uid, None)
            h._send(json.dumps({'ok': True, 'jobs': len(records), 'path': str(out_path)}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    return False
