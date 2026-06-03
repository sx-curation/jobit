#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Job Tracker local server — stdlib only, no pip installs required.
Run:  python scripts/server.py
Opens: http://localhost:8080
'''
import sys, io, json, os, re, socketserver, threading, webbrowser, copy, time, subprocess, shutil
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import defaultdict, Counter
from datetime import datetime

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass
try:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_DIR  = Path(__file__).resolve().parent.parent
USERS_DIR    = PROJECT_DIR / 'users'
USERS_JSON   = PROJECT_DIR / 'users.json'
HTML_PATH    = Path("C:/Users/Admin/Desktop/job_tracker/index.html")
PORT         = 8080
_write_lock      = threading.Lock()
ANSI_RE          = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
_search_proc     = None
_search_log      = []
_search_lock     = threading.Lock()
_jobs_cache: dict       = {}   # uid → list[dict]
_jobs_cache_mtime: dict = {}   # uid → float
_jobs_cache_lock = threading.Lock()
_current_user    = 'leon'
_user_lock       = threading.Lock()

# ── Multi-user path helpers ───────────────────────────────────────────────────
def _cur_uid() -> str:
    with _user_lock: return _current_user

def _user_dir(uid: str) -> Path:
    return USERS_DIR / uid

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


def _to_str_list(items) -> list:
    """Normalize old-format object arrays or new-format string arrays to plain strings."""
    result = []
    for item in (items or []):
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            result.append(
                item.get('responsibility') or item.get('skill') or item.get('gap') or ''
            )
    return [s for s in result if s]


# ── Parse + merge job data ────────────────────────────────────────────────────
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

    # Build group_id → group_label lookup from config
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

        # Score cell: [**97**](path/jd_analysis.json)  — path may contain ()
        score_cell = cells[1]
        sm = re.search(r'\*?\*?(\d+(?:\.\d+)?)\*?\*?\]\((.+?jd_analysis\.json)\)', score_cell)
        if sm:
            score_val = float(sm.group(1))
            jd_rel    = sm.group(2)
        else:
            sm2 = re.search(r'(\d+(?:\.\d+)?)', score_cell)
            score_val = float(sm2.group(1)) if sm2 else None
            jd_rel    = None

        # URL cell: [Link](https://...)
        url_cell = cells[7] if len(cells) > 7 else ''
        um = re.search(r'\[Link\]\(([^)]+)\)', url_cell)
        url = um.group(1) if um else ''

        # Emphasis / missing_skills — strip trailing " +N" indicator
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
            # detail fields (filled below)
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
        })

    # Merge jd_analysis.json for each job
    for job in jobs:
        if not job['jd_path']:
            continue
        jd_file = output_dir / job['jd_path']
        if not jd_file.exists():
            continue
        try:
            detail = json.loads(jd_file.read_text(encoding='utf-8'))
            job['application_record']    = detail.get('application_record', None)
            job['core_responsibilities'] = _to_str_list(detail.get('core_responsibilities', []))
            job['culture_keywords']      = detail.get('culture_keywords', [])
            job['matched_skills']        = detail.get('matched_skills', [])
            raw_ms = detail.get('missing_skills', [])
            job['missing_skills']        = [
                item if isinstance(item, dict) else {'skill': item, 'severity': 'unknown'}
                for item in raw_ms if item
            ]
            job['bonus_skills']          = detail.get('bonus_skills', [])
            job['required_skills']       = _to_str_list(detail.get('required_skills', []))
            job['recommended_emphasis']  = detail.get('recommended_emphasis', [])
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
        except Exception as e:
            print(f'  WARN {jd_file.name}: {e}', file=sys.stderr)

    # Check if CV + CL materials have been generated
    for job in jobs:
        if not job['jd_path']:
            continue
        job_dir = output_dir / Path(job['jd_path']).parent
        job['materials_ready'] = (job_dir / 'cv_ats.pdf').exists() or (job_dir / 'cv_final.pdf').exists()

    # ── Load raw (unanalyzed) candidates from temp raw_results files ────────────
    TEMP_DIR = output_dir / 'temp'
    analyzed_keys: set[tuple] = set()
    for job in jobs:
        analyzed_keys.add((job['company'].strip().lower(), job['title'].strip().lower()[:60]))

    cfg_for_raw = read_config(uid)
    _, kgs_raw, _ = get_keyword_groups(cfg_for_raw, uid)
    group_label_map_raw = {g.get('group_id', ''): g.get('group_label', g.get('group_id', '')) for g in kgs_raw}

    raw_seen: set[tuple] = set()

    if TEMP_DIR.exists():
        for raw_file in sorted(TEMP_DIR.glob('raw_results_*.json'), reverse=True):
            try:
                raw_jobs = json.loads(raw_file.read_text(encoding='utf-8'))
            except Exception:
                continue
            for rj in raw_jobs:
                company = (rj.get('company') or '').strip()
                title   = (rj.get('title')   or '').strip()
                if not company or not title:
                    continue
                key = (company.lower(), title.lower()[:60])
                if key in analyzed_keys or key in raw_seen:
                    continue
                raw_seen.add(key)
                source = rj.get('_source', 'linkedin')
                src_label = 'Stepstone' if source == 'stepstone' else 'LinkedIn'
                gid = rj.get('_group_id', '')
                score_preview = rj.get('match_score_preview')
                jobs.append({
                    'row':                      '',
                    'score':                    score_preview,
                    'jd_path':                  None,
                    'group':                    gid,
                    'group_label':              group_label_map_raw.get(gid, gid),
                    'source':                   src_label,
                    'company':                  company,
                    'title':                    title,
                    'size':                     '',
                    'location':                 rj.get('location', ''),
                    'inferred_location':        rj.get('_zip_label', rj.get('location', '')),
                    'url':                      rj.get('url', ''),
                    'recommended_emphasis_raw': '',
                    'missing_skills_raw':       '',
                    'analyzed':                 '—',
                    'remark':                   'unanalyzed',
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
                })

    # Detect cross-source duplicates → remark = "multiple source"
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


# ── Config helpers ────────────────────────────────────────────────────────────
def read_config(uid: str):
    return json.loads(get_config_path(uid).read_text(encoding='utf-8'))

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
        uid = uid or _cur_uid()
        data = read_config(uid)
    cfg = data
    if 'keyword_groups' in cfg:
        return cfg, cfg['keyword_groups'], ['keyword_groups']
    js = cfg.get('job_search', {})
    if 'keyword_groups' in js:
        return cfg, js['keyword_groups'], ['job_search', 'keyword_groups']
    return cfg, [], []


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
                matched_all.extend(detail.get('matched_skills', []))
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
        good     = sum(1 for s in scores_list if 50 <= s < 70)
        moderate = sum(1 for s in scores_list if 30 <= s < 50)

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


# ── Search subprocess ────────────────────────────────────────────────────────
_SEARCH_MAX_S = 1800  # 30 分钟硬上限

# ── ATS Field Map (form-assist) ───────────────────────────────────────────────
_ATS_FIELD_MAP = {
    "workday": {
        "work_experience": [
            {"key": "company",     "label": "Employer"},
            {"key": "title",       "label": "Job Title"},
            {"key": "start_month", "label": "Start Month (MM)"},
            {"key": "start_year",  "label": "Start Year (YYYY)"},
            {"key": "end_month",   "label": "End Month (MM)",      "optional": True},
            {"key": "end_year",    "label": "End Year (YYYY)"},
            {"key": "country",     "label": "Country"},
            {"key": "city",        "label": "City"},
            {"key": "desc_short",  "label": "Description (1 line)"},
            {"key": "desc_full",   "label": "Description (full)"},
        ],
        "education": [
            {"key": "institution", "label": "School / Institution"},
            {"key": "degree",      "label": "Degree"},
            {"key": "field",       "label": "Field of Study"},
            {"key": "start_year",  "label": "Start Year"},
            {"key": "end_year",    "label": "End Year"},
            {"key": "gpa",         "label": "GPA",                 "optional": True},
        ],
    },
    "sap_custom": {
        "work_experience": [
            {"key": "company",     "label": "Unternehmen / Company"},
            {"key": "title",       "label": "Stelle / Job Title"},
            {"key": "start_month", "label": "Von (MM)"},
            {"key": "start_year",  "label": "Von (JJJJ)"},
            {"key": "end_month",   "label": "Bis (MM)",            "optional": True},
            {"key": "end_year",    "label": "Bis (JJJJ)"},
            {"key": "country",     "label": "Land / Country"},
            {"key": "city",        "label": "Stadt / City"},
            {"key": "desc_full",   "label": "Aufgaben / Responsibilities"},
        ],
        "education": [
            {"key": "institution", "label": "Bildungseinrichtung"},
            {"key": "degree",      "label": "Abschluss"},
            {"key": "field",       "label": "Fachrichtung"},
            {"key": "start_year",  "label": "Von (JJJJ)"},
            {"key": "end_year",    "label": "Bis (JJJJ)"},
        ],
    },
    "greenhouse": {
        "work_experience": [
            {"key": "company",     "label": "Company"},
            {"key": "title",       "label": "Title"},
            {"key": "start_month", "label": "Start Month"},
            {"key": "start_year",  "label": "Start Year"},
            {"key": "end_month",   "label": "End Month",           "optional": True},
            {"key": "end_year",    "label": "End Year"},
            {"key": "desc_full",   "label": "Job Description"},
        ],
        "education": [
            {"key": "institution", "label": "School"},
            {"key": "degree",      "label": "Degree"},
            {"key": "field",       "label": "Discipline"},
            {"key": "start_year",  "label": "Start Year"},
            {"key": "end_year",    "label": "End Year"},
        ],
    },
    "lever": {
        "work_experience": [
            {"key": "company",     "label": "Employer"},
            {"key": "title",       "label": "Position"},
            {"key": "start_year",  "label": "Year Started"},
            {"key": "end_year",    "label": "Year Ended"},
            {"key": "desc_full",   "label": "Summary"},
        ],
        "education": [
            {"key": "institution", "label": "University"},
            {"key": "degree",      "label": "Degree"},
            {"key": "field",       "label": "Major"},
            {"key": "end_year",    "label": "Graduation Year"},
        ],
    },
}
_ATS_FIELD_MAP["generic"] = _ATS_FIELD_MAP["workday"]   # fallback alias


def _parse_duration(duration: str) -> dict:
    '''Parse "2024", "2024 – 2025", "09/2024 – 12/2025" → {start_year, start_month, end_year, end_month}.'''
    parts = re.split(r'\s*[–—\-]\s*', str(duration).strip(), maxsplit=1)
    def _part(s):
        s = s.strip()
        m = re.match(r'(\d{1,2})[/.](\d{4})$', s)
        if m:
            return m.group(2), m.group(1).zfill(2)
        m = re.match(r'(\d{4})$', s)
        if m:
            return m.group(1), ''
        if re.search(r'present|current|heute|bis heute', s, re.I):
            return 'Present', ''
        return s, ''
    sy, sm = _part(parts[0]) if parts else ('', '')
    ey, em = _part(parts[1]) if len(parts) > 1 else ('', '')
    return {'start_year': sy, 'start_month': sm, 'end_year': ey, 'end_month': em}


def _build_form_fields(cv_parsed: dict, ats_type: str, jd_data: dict | None = None) -> dict:
    '''Map cv_parsed to ATS form field cards, optionally reordering bullets by JD relevance.'''
    fmap = _ATS_FIELD_MAP.get(ats_type, _ATS_FIELD_MAP['workday'])

    matched_kws = [s.lower() for s in (jd_data or {}).get('matched_skills', [])] if jd_data else []

    def _score_bullet(bullet: str) -> int:
        b = bullet.lower()
        return sum(1 for kw in matched_kws if kw in b)

    def _exp_cards(exp_list):
        cards = []
        for exp in exp_list:
            dur = _parse_duration(exp.get('duration', ''))
            bullets = exp.get('bullets', [])
            if matched_kws and bullets:
                bullets = sorted(bullets, key=_score_bullet, reverse=True)
            raw = {
                'company':     exp.get('company', ''),
                'title':       exp.get('title', ''),
                'start_month': dur['start_month'],
                'start_year':  dur['start_year'],
                'end_month':   dur['end_month'],
                'end_year':    dur['end_year'],
                'country':     'Germany',
                'city':        '',
                'desc_short':  (bullets[0][:120] if bullets else ''),
                'desc_full':   '\n'.join(bullets),
            }
            fields = []
            for f in fmap.get('work_experience', []):
                val = raw.get(f['key'], '')
                if f.get('optional') and not val:
                    continue
                fields.append({'label': f['label'], 'value': val, 'key': f['key']})
            cards.append({'header': exp.get('company', ''), 'fields': fields})
        return cards

    def _edu_cards(edu_list):
        cards = []
        for edu in edu_list:
            dur = _parse_duration(edu.get('duration', edu.get('years', '')))
            raw = {
                'institution': edu.get('institution', edu.get('school', '')),
                'degree':      edu.get('degree', ''),
                'field':       edu.get('field', edu.get('major', '')),
                'start_year':  dur['start_year'],
                'end_year':    dur['end_year'],
                'gpa':         str(edu.get('gpa', '')),
            }
            fields = []
            for f in fmap.get('education', []):
                val = raw.get(f['key'], '')
                if f.get('optional') and not val:
                    continue
                fields.append({'label': f['label'], 'value': val, 'key': f['key']})
            cards.append({'header': raw['institution'], 'fields': fields})
        return cards

    return {
        'ats_type': ats_type,
        'work_experience': _exp_cards(cv_parsed.get('experience', [])),
        'education': _edu_cards(cv_parsed.get('education', [])),
    }

def _run_search(cmd, uid: str):
    global _search_proc, _search_log
    claude_bin = shutil.which('claude') or 'claude'
    with _search_lock:
        _search_log = []
        _search_proc = subprocess.Popen(
            [claude_bin, '-p', cmd],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=str(_user_dir(uid)), text=True,
            encoding='utf-8', errors='replace',
        )

    def _watchdog():
        time.sleep(_SEARCH_MAX_S)
        proc = _search_proc
        if proc and proc.poll() is None:
            proc.kill()
            _search_log.append('[TIMEOUT] Search process killed after 30 min')
    threading.Thread(target=_watchdog, daemon=True).start()

    try:
        for line in _search_proc.stdout:
            stripped = ANSI_RE.sub('', line.rstrip())
            if stripped and len(_search_log) < 5000:
                _search_log.append(stripped)
    finally:
        _search_proc.wait()


# ── User registry helpers ────────────────────────────────────────────────────
def _load_users() -> dict:
    '''Read users.json; return {"users": []} if missing/invalid.'''
    if not USERS_JSON.exists():
        return {"users": []}
    try:
        return json.loads(USERS_JSON.read_text(encoding='utf-8'))
    except Exception:
        return {"users": []}

def _register_user(uid: str, name: str):
    '''Append user to users.json (write-lock protected).'''
    with _write_lock:
        registry = _load_users()
        if any(u['id'] == uid for u in registry['users']):
            return
        registry['users'].append({'id': uid, 'name': name})
        USERS_JSON.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding='utf-8')


# ── LLM job family generation ─────────────────────────────────────────────────
def _build_job_family_prompt(group: dict) -> str:
    label  = group.get('group_label', group.get('group_id', ''))
    en_kws = ', '.join(group.get('primary_keywords', {}).get('en', []))
    de_kws = ', '.join(group.get('primary_keywords', {}).get('de', []))
    return (
        'You are a German job-market recruiter familiar with LinkedIn DE, StepStone, and XING.\n\n'
        f'Group label: {label}\n'
        f'Primary keywords EN: {en_kws}\n'
        f'Primary keywords DE: {de_kws}\n'
        'Target market: Germany\n\n'
        'Generate 15-18 English and 13-16 German additional job titles that:\n'
        '1. Are used by real German employers (not invented titles)\n'
        '2. Cover adjacent specializations and seniority levels in the same domain\n'
        '3. Use authentic German conventions (compound nouns, no "(m/w/d)")\n'
        '4. Do NOT repeat the primary keywords above\n\n'
        'Output ONLY valid JSON, no markdown, no explanation:\n'
        '{"en": ["Title 1", ...], "de": ["Titel 1", ...]}'
    )

def _run_generate_job_family(group: dict) -> tuple:
    '''Returns (result_dict, None) or (None, error_dict). Blocking ~15s.'''
    prompt = _build_job_family_prompt(group)
    claude_bin = shutil.which('claude') or 'claude'
    try:
        proc = subprocess.run(
            [claude_bin, '-p', prompt],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=90, cwd=str(PROJECT_DIR)
        )
    except subprocess.TimeoutExpired:
        return None, {'message': 'Claude timed out after 90s', 'raw': ''}
    except FileNotFoundError:
        return None, {'message': 'claude binary not found', 'raw': ''}

    raw = ANSI_RE.sub('', proc.stdout.strip())
    m = re.search(r'\{[\s\S]*\}', raw)
    if not m:
        return None, {'message': 'No JSON found in output', 'raw': raw[:500]}
    try:
        result = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return None, {'message': f'JSON parse error: {e}', 'raw': raw[:500]}
    if not isinstance(result.get('en'), list) or not isinstance(result.get('de'), list):
        return None, {'message': 'Invalid shape: expected {"en":[...],"de":[...]}', 'raw': raw[:200]}
    result['en'] = result['en'][:25]
    result['de'] = result['de'][:25]
    return result, None


# ── HTTP request handler ──────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def _read_json_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(length).decode('utf-8'))

    def _send(self, body, content_type='application/json', status=200):
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        uid = _cur_uid()

        if path in ('/', '/index.html'):
            if HTML_PATH.exists():
                self._send(HTML_PATH.read_bytes(), 'text/html')
            else:
                self._send(
                    b'<h2>index.html not found.<br>Run: python scripts/gen_job_tracker_html.py</h2>',
                    'text/html', 404
                )

        elif path == '/api/jobs':
            try:
                jobs = parse_jobs(uid)
                self._send(json.dumps(jobs, ensure_ascii=False))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/status':
            try:
                js = get_job_summary(uid)
                mtime = js.stat().st_mtime if js.exists() else 0.0
                self._send(json.dumps({'mtime': mtime}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/group-stats':
            try:
                self._send(json.dumps(compute_group_stats(uid), ensure_ascii=False))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/search-analysis':
            try:
                self._send(json.dumps(compute_search_analysis(uid), ensure_ascii=False))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/cvfiles':
            try:
                cv_dir = get_cv_dir(uid)
                files = sorted(p.name for p in cv_dir.glob('*.pdf')) if cv_dir.exists() else []
                self._send(json.dumps(files))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/cvfile':
            try:
                name = parse_qs(urlparse(self.path).query).get('name', [''])[0]
                if not name or '/' in name or '\\' in name or '..' in name:
                    self._send(b'Bad request', 'text/plain', 400)
                    return
                fpath = get_cv_dir(uid) / name
                if not fpath.exists() or not fpath.is_file():
                    self._send(b'Not found', 'text/plain', 404)
                    return
                self._send(fpath.read_bytes(), 'application/pdf')
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/search-status':
            running = bool(_search_proc and _search_proc.poll() is None)
            self._send(json.dumps({'running': running}))

        elif path == '/api/search-log':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            sent = 0
            deadline = time.monotonic() + _SEARCH_MAX_S + 60
            try:
                while time.monotonic() < deadline:
                    while sent < len(_search_log):
                        data = json.dumps({'text': _search_log[sent]}, ensure_ascii=False)
                        self.wfile.write(f'data: {data}\n\n'.encode('utf-8'))
                        self.wfile.flush()
                        sent += 1
                    if _search_proc and _search_proc.poll() is not None and sent >= len(_search_log):
                        self.wfile.write(b'data: {"done":true}\n\n')
                        self.wfile.flush()
                        break
                    time.sleep(0.3)
                else:
                    self.wfile.write(b'data: {"timeout":true}\n\n')
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        elif path == '/api/users':
            try:
                registry = _load_users()
                self._send(json.dumps({
                    'current': uid,
                    'users': registry.get('users', [])
                }, ensure_ascii=False))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/taxonomy':
            try:
                cfg = read_config(uid)
                taxonomy = cfg.get('skill_taxonomy', {})
                self._send(json.dumps(taxonomy, ensure_ascii=False))
            except Exception as e:
                self._send(json.dumps({}))  # silent fallback

        elif path == '/api/form-fields':
            try:
                qs = parse_qs(urlparse(self.path).query)
                job_folder = qs.get('job_folder', [''])[0].strip()
                ats_type   = qs.get('ats_type', ['workday'])[0].strip()
                if not job_folder:
                    self._send(json.dumps({'error': 'job_folder required'}), status=400)
                    return
                output_dir = get_output_dir(uid)
                job_path = (output_dir / job_folder).resolve()
                # Path traversal guard
                try:
                    job_path.relative_to(output_dir.resolve())
                except ValueError:
                    self._send(json.dumps({'error': 'invalid path'}), status=400)
                    return
                jd_file = job_path / 'jd_analysis.json'
                if not jd_file.exists():
                    self._send(json.dumps({'error': 'jd_analysis.json not found'}), status=404)
                    return
                group_id = job_folder.split('_')[0]
                cv_file = get_output_dir(uid) / f'cv_parsed_{group_id}.json'
                if not cv_file.exists():
                    self._send(json.dumps({'error': f'cv_parsed not found: {group_id}'}), status=404)
                    return
                cv_parsed = json.loads(cv_file.read_text(encoding='utf-8'))
                jd_data   = json.loads(jd_file.read_text(encoding='utf-8'))
                result = _build_form_fields(cv_parsed, ats_type, jd_data)
                result['recommended_emphasis'] = jd_data.get('recommended_emphasis', [])
                result['matched_skills']       = jd_data.get('matched_skills', [])
                result['exp_optimized']        = jd_data.get('exp_optimized', {})
                self._send(json.dumps(result, ensure_ascii=False))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        else:
            self._send(b'Not found', 'text/plain', 404)

    def do_POST(self):
        global _current_user
        path = urlparse(self.path).path
        uid = _cur_uid()

        if path == '/api/record':
            try:
                data = self._read_json_body()
                result, status = _update_jd_field(data.get('jd_path'), 'application_record', data.get('record'), uid)
                self._send(json.dumps(result), status=status)
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/note':
            try:
                data = self._read_json_body()
                result, status = _update_jd_field(data.get('jd_path'), 'user_note', data.get('note', ''), uid)
                self._send(json.dumps(result), status=status)
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/group-delete':
            try:
                data = self._read_json_body()
                gid    = data.get('group_id', '').strip()
                if not gid:
                    self._send(json.dumps({'error': 'group_id required'}), status=400)
                    return
                cfg, groups, path_keys = get_keyword_groups(uid=uid)
                new_groups = [g for g in groups if g.get('group_id') != gid]
                if len(new_groups) == len(groups):
                    self._send(json.dumps({'error': f'group_id not found: {gid}'}), status=404)
                    return
                _set_nested(cfg, path_keys, new_groups)
                write_config(cfg, uid)
                self._send(json.dumps({'ok': True}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/group-dup':
            try:
                data = self._read_json_body()
                gid    = data.get('group_id', '').strip()
                if not gid:
                    self._send(json.dumps({'error': 'group_id required'}), status=400)
                    return
                cfg, groups, path_keys = get_keyword_groups(uid=uid)
                originals = [g for g in groups if g.get('group_id') == gid]
                if not originals:
                    self._send(json.dumps({'error': f'group_id not found: {gid}'}), status=404)
                    return
                new_grp   = copy.deepcopy(originals[0])
                taken     = {g.get('group_id', '') for g in groups}
                base      = gid + '-copy'
                new_id    = base
                i = 2
                while new_id in taken:
                    new_id = f'{base}-{i}'
                    i += 1
                new_grp['group_id']    = new_id
                new_grp['group_label'] = new_grp.get('group_label', gid) + ' (Copy)'
                groups.append(new_grp)
                _set_nested(cfg, path_keys, groups)
                write_config(cfg, uid)
                self._send(json.dumps({'ok': True, 'new_group_id': new_id}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/group-save':
            try:
                data = self._read_json_body()
                grp = data.get('group')
                if not grp or not grp.get('group_id'):
                    self._send(json.dumps({'error': 'group_id required'}), status=400)
                    return
                gid = grp['group_id'].strip()
                if not gid:
                    self._send(json.dumps({'error': 'group_id must not be empty'}), status=400)
                    return
                cfg, groups, path_keys = get_keyword_groups(uid=uid)
                if any(g.get('group_id') == gid for g in groups):
                    self._send(json.dumps({'error': f'group_id already exists: {gid}'}), status=409)
                    return
                groups.append(grp)
                _set_nested(cfg, path_keys, groups)
                write_config(cfg, uid)
                self._send(json.dumps({'ok': True, 'group_id': gid}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/search':
            try:
                data = self._read_json_body()
                group_id = data.get('group_id', 'all')
                cfg = read_config(uid)
                _, kgs, _ = get_keyword_groups(cfg, uid)
                valid_ids = {g.get('group_id') for g in kgs}
                if group_id != 'all' and group_id not in valid_ids:
                    self._send(json.dumps({'error': 'invalid group_id'}), status=400)
                    return
                with _search_lock:
                    if _search_proc and _search_proc.poll() is None:
                        self._send(json.dumps({'error': 'search already running'}), status=409)
                        return
                cmd = f'搜索职缺 {group_id}' if group_id != 'all' else '搜索职缺'
                threading.Thread(target=_run_search, args=(cmd, uid), daemon=True).start()
                self._send(json.dumps({'ok': True, 'cmd': cmd}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/switch-user':
            try:
                data = self._read_json_body()
                new_uid = (data.get('user_id') or '').strip()
                if not new_uid:
                    self._send(json.dumps({'error': 'user_id required'}), status=400)
                    return
                with _search_lock:
                    if _search_proc and _search_proc.poll() is None:
                        self._send(json.dumps({'error': 'search_running'}), status=409)
                        return
                if not (USERS_DIR / new_uid).is_dir():
                    self._send(json.dumps({'error': f'user not found: {new_uid}'}), status=404)
                    return
                with _user_lock:
                    _current_user = new_uid
                self._send(json.dumps({'ok': True, 'user_id': new_uid}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/create-user':
            try:
                data = self._read_json_body()
                name   = (data.get('name') or '').strip()
                new_uid = (data.get('user_id') or '').strip()
                if not name or not new_uid:
                    self._send(json.dumps({'error': 'name and user_id required'}), status=400)
                    return
                if re.search(r'[^a-z0-9\-_]', new_uid):
                    self._send(json.dumps({'error': 'user_id must be lowercase alphanumeric'}), status=400)
                    return
                if (USERS_DIR / new_uid).exists():
                    self._send(json.dumps({'error': f'user already exists: {new_uid}'}), status=409)
                    return
                # Create workspace inline (avoid import complexity)
                user_dir = USERS_DIR / new_uid
                (user_dir / 'output' / 'temp').mkdir(parents=True, exist_ok=True)
                (user_dir / 'my_cv').mkdir(exist_ok=True)
                (user_dir / 'memory').mkdir(exist_ok=True)
                for jname in ['.claude', 'scripts', 'graphify-out']:
                    link = user_dir / jname
                    target = PROJECT_DIR / jname
                    if target.exists() and not link.exists():
                        subprocess.run(
                            ['cmd', '/c', 'mklink', '/J', str(link), str(target)],
                            capture_output=True
                        )
                for fname in ['SPEC.md']:
                    src = PROJECT_DIR / fname
                    dst = user_dir / fname
                    if src.exists() and not dst.exists():
                        try:
                            os.link(src, dst)
                        except OSError:
                            import shutil as _sh
                            _sh.copy2(src, dst)
                cfg_path = user_dir / 'config.json'
                if not cfg_path.exists():
                    template = {"job_search": {"keyword_groups": []}, "skill_taxonomy": {}}
                    cfg_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding='utf-8')
                _register_user(new_uid, name)
                self._send(json.dumps({'ok': True, 'user_id': new_uid}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/generate-job-family':
            try:
                data = self._read_json_body()
                gid = (data.get('group_id') or '').strip()
                cfg, groups, _ = get_keyword_groups(uid=uid)
                target = next((g for g in groups if g.get('group_id') == gid), None)
                if not target:
                    self._send(json.dumps({'error': f'group not found: {gid}'}), status=404)
                    return
                result, err = _run_generate_job_family(target)
                if err:
                    self._send(json.dumps({'error': err['message'], 'raw': err.get('raw', '')}), status=500)
                else:
                    self._send(json.dumps({'ok': True, 'result': result}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/save-job-family':
            try:
                data = self._read_json_body()
                gid = (data.get('group_id') or '').strip()
                jf  = data.get('job_family')
                if not gid or jf is None:
                    self._send(json.dumps({'error': 'group_id and job_family required'}), status=400)
                    return
                cfg, groups, path_keys = get_keyword_groups(uid=uid)
                target = next((g for g in groups if g.get('group_id') == gid), None)
                if not target:
                    self._send(json.dumps({'error': f'group not found: {gid}'}), status=404)
                    return
                target['job_family'] = jf
                _set_nested(cfg, path_keys, groups)
                write_config(cfg, uid)
                self._send(json.dumps({'ok': True}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/form-assist':
            try:
                data      = self._read_json_body()
                job_folder = (data.get('job_folder') or '').strip()
                form_fields = [f for f in (data.get('form_fields') or []) if str(f).strip()]
                if not job_folder:
                    self._send(json.dumps({'error': 'job_folder required'}), status=400)
                    return
                output_dir = get_output_dir(uid)
                job_path   = (output_dir / job_folder).resolve()
                try:
                    job_path.relative_to(output_dir.resolve())
                except ValueError:
                    self._send(json.dumps({'error': 'invalid job_folder path'}), status=400)
                    return
                if not job_path.is_dir():
                    self._send(json.dumps({'error': f'not found: {job_folder}'}), status=404)
                    return
                fields_text = '\n'.join(f'- {f}' for f in form_fields)
                prompt = (
                    f'表单助手\n'
                    f'job_folder: "{job_folder}"\n'
                    f'form_fields:\n{fields_text}'
                )
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                claude_bin = shutil.which('claude') or 'claude'
                proc = subprocess.Popen(
                    [claude_bin, '-p', prompt],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(_user_dir(uid)), text=True,
                    encoding='utf-8', errors='replace',
                )
                try:
                    for line in proc.stdout:
                        stripped = ANSI_RE.sub('', line.rstrip())
                        if stripped:
                            chunk = json.dumps({'text': stripped}, ensure_ascii=False)
                            self.wfile.write(f'data: {chunk}\n\n'.encode('utf-8'))
                            self.wfile.flush()
                    proc.wait()
                    self.wfile.write(b'data: {"done":true}\n\n')
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            except Exception as e:
                try:
                    err = json.dumps({'error': str(e)}, ensure_ascii=False)
                    self.wfile.write(f'data: {err}\n\n'.encode('utf-8'))
                    self.wfile.flush()
                except Exception:
                    pass

        elif path == '/api/optimize-exp':
            try:
                import tempfile as _tmpmod
                data       = self._read_json_body()
                job_folder = (data.get('job_folder') or '').strip()
                exp_header = (data.get('exp_header') or '').strip()
                desc_full  = (data.get('desc_full') or '').strip()
                if not job_folder:
                    self._send(json.dumps({'error': 'job_folder required'}), status=400); return
                # Read JD context for a self-contained prompt
                jd_ctx = {}
                try:
                    _jd_p = get_output_dir(uid) / job_folder / 'jd_analysis.json'
                    if _jd_p.exists():
                        jd_ctx = json.loads(_jd_p.read_text(encoding='utf-8'))
                except Exception:
                    pass
                matched  = ', '.join((jd_ctx.get('matched_skills') or [])[:8])
                emphasis = '\n'.join(f'- {e}' for e in (jd_ctx.get('recommended_emphasis') or [])[:3])
                prompt = (
                    f'You are an ATS resume expert. Rewrite the following work experience bullets '
                    f'for a "{jd_ctx.get("title","")}" role at {jd_ctx.get("company","")}.\n\n'
                    f'JD matched skills: {matched}\n\n'
                    f'Recommended emphasis:\n{emphasis}\n\n'
                    f'Original bullets for {exp_header}:\n{desc_full}\n\n'
                    f'Rules (MUST follow):\n'
                    f'- Only use content from the original bullets — no fabrication\n'
                    f'- Put the most JD-relevant bullet first\n'
                    f'- Inject at most 2 JD keywords naturally into existing text\n'
                    f'- Remove clichés: leveraged, facilitated, synergies, spearheaded\n'
                    f'- Use varied action verbs (not repeated managed/led)\n'
                    f'- Preserve all numbers and metrics exactly\n\n'
                    f'Output ONLY the rewritten bullets, one per line starting with a verb. '
                    f'No headers, no explanation, no markdown.'
                )
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                claude_bin = shutil.which('claude') or 'claude'
                proc = subprocess.Popen(
                    [claude_bin, '-p', prompt,
                     '--disallowedTools', 'Read,Glob,Grep,Write,Edit,WebFetch,WebSearch,TodoWrite,TodoRead'],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    cwd=_tmpmod.gettempdir(), text=True,
                    encoding='utf-8', errors='replace',
                )
                try:
                    full_lines = []
                    _skip_prefixes = ('Warning:', 'The `', "To use it,", "Which would", "1. **", "2. **", "Available", "Please tell")
                    for line in proc.stdout:
                        stripped = ANSI_RE.sub('', line.rstrip())
                        if stripped and not any(stripped.startswith(p) for p in _skip_prefixes):
                            full_lines.append(stripped)
                            chunk = json.dumps({'text': stripped + '\n'}, ensure_ascii=False)
                            self.wfile.write(f'data: {chunk}\n\n'.encode('utf-8'))
                            self.wfile.flush()
                    proc.wait()
                    # Save to jd_analysis.json cache
                    if full_lines and job_folder and exp_header:
                        jd_path = get_output_dir(uid) / job_folder / 'jd_analysis.json'
                        if jd_path.exists():
                            try:
                                jd = json.loads(jd_path.read_text(encoding='utf-8'))
                                if 'exp_optimized' not in jd:
                                    jd['exp_optimized'] = {}
                                jd['exp_optimized'][exp_header] = '\n'.join(full_lines)
                                jd_path.write_text(json.dumps(jd, ensure_ascii=False, indent=2), encoding='utf-8')
                            except Exception:
                                pass
                    self.wfile.write(b'data: {"done":true}\n\n')
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            except Exception as e:
                try:
                    self.wfile.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode('utf-8'))
                    self.wfile.flush()
                except Exception:
                    pass

        elif path == '/api/default-answers':
            try:
                data       = self._read_json_body()
                job_folder = (data.get('job_folder') or '').strip()
                if not job_folder:
                    self._send(json.dumps({'error': 'job_folder required'}), status=400); return
                # Return cached result if available
                jd_file = get_output_dir(uid) / job_folder / 'jd_analysis.json'
                if jd_file.exists():
                    jd = json.loads(jd_file.read_text(encoding='utf-8'))
                    cached = jd.get('default_answers')
                    if cached:
                        self._send(json.dumps({'cached': True, 'default_answers': cached}, ensure_ascii=False))
                        return
                # Stream generate
                prompt = f'default-answers\njob_folder: "{job_folder}"'
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                claude_bin = shutil.which('claude') or 'claude'
                proc = subprocess.Popen(
                    [claude_bin, '-p', prompt],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(_user_dir(uid)), text=True,
                    encoding='utf-8', errors='replace',
                )
                try:
                    for line in proc.stdout:
                        stripped = ANSI_RE.sub('', line.rstrip())
                        if stripped:
                            chunk = json.dumps({'text': stripped}, ensure_ascii=False)
                            self.wfile.write(f'data: {chunk}\n\n'.encode('utf-8'))
                            self.wfile.flush()
                    proc.wait()
                    self.wfile.write(b'data: {"done":true}\n\n')
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            except Exception as e:
                try:
                    self.wfile.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode('utf-8'))
                    self.wfile.flush()
                except Exception:
                    pass

        elif path == '/api/finetune-answer':
            try:
                data        = self._read_json_body()
                job_folder  = (data.get('job_folder') or '').strip()
                question    = (data.get('question') or '').strip()
                cur_answer  = (data.get('current_answer') or '').strip()
                direction   = (data.get('direction') or '').strip()
                if not job_folder:
                    self._send(json.dumps({'error': 'job_folder required'}), status=400); return
                prompt = (
                    f'default-answers\n'
                    f'job_folder: "{job_folder}"\n'
                    f'finetune: true\n'
                    f'question: {question}\n'
                    f'current_answer: {cur_answer}\n'
                    f'direction: {direction}'
                )
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                claude_bin = shutil.which('claude') or 'claude'
                proc = subprocess.Popen(
                    [claude_bin, '-p', prompt],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(_user_dir(uid)), text=True,
                    encoding='utf-8', errors='replace',
                )
                try:
                    for line in proc.stdout:
                        stripped = ANSI_RE.sub('', line.rstrip())
                        if stripped:
                            chunk = json.dumps({'text': stripped}, ensure_ascii=False)
                            self.wfile.write(f'data: {chunk}\n\n'.encode('utf-8'))
                            self.wfile.flush()
                    proc.wait()
                    self.wfile.write(b'data: {"done":true}\n\n')
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            except Exception as e:
                try:
                    self.wfile.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode('utf-8'))
                    self.wfile.flush()
                except Exception:
                    pass

        else:
            self._send(json.dumps({'error': 'Not found'}), status=404)

    def log_message(self, fmt, *args):
        if args and str(args[1]) not in ('200', '204', '304'):
            print(f'  {self.address_string()} {fmt % args}', file=sys.stderr)


# ── JD file helpers ──────────────────────────────────────────────────────────
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
    return {'ok': True}, 200


# ── Threading server ──────────────────────────────────────────────────────────
class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Load first registered user as default
    if USERS_JSON.exists():
        try:
            registry = json.loads(USERS_JSON.read_text(encoding='utf-8'))
            if registry.get('users'):
                with _user_lock:
                    _current_user = registry['users'][0]['id']
        except Exception:
            pass

    # Auto-generate HTML if missing
    if not HTML_PATH.exists():
        print(f'Generating {HTML_PATH} ...')
        HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            import runpy
            runpy.run_path(str(PROJECT_DIR / 'scripts' / 'gen_job_tracker_html.py'))
            print('HTML generated.')
        except Exception as _e:
            print(f'  [WARN] Could not auto-generate HTML: {_e}', file=sys.stderr)
            print('  Run manually: python scripts/gen_job_tracker_html.py', file=sys.stderr)

    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    url    = f'http://localhost:{PORT}'
    print(f'Job Tracker  →  {url}')
    print(f'HTML:  {HTML_PATH}')
    uid = _cur_uid()
    print(f'User:  {uid}  (data: {_user_dir(uid)})')
    print('Ctrl+C to stop.\n')
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped.')
