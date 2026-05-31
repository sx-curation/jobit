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
HTML_PATH    = Path("C:/Users/Leon/Desktop/job_tracker/index.html")
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
            job['core_responsibilities'] = detail.get('core_responsibilities', [])
            job['culture_keywords']      = detail.get('culture_keywords', [])
            job['matched_skills']        = detail.get('matched_skills', [])
            job['missing_skills']        = detail.get('missing_skills', [])
            job['bonus_skills']          = detail.get('bonus_skills', [])
            job['required_skills']       = detail.get('required_skills', [])
            job['recommended_emphasis']  = detail.get('recommended_emphasis', [])
            job['user_note']             = detail.get('user_note', '')
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
        job['materials_ready'] = (job_dir / 'cv_final.pdf').exists()

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
                missing_all.extend(detail.get('missing_skills', []))
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
