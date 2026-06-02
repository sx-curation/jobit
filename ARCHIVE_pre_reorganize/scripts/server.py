#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Job Tracker local server — stdlib only, no pip installs required.
Run:  python scripts/server.py
Opens: http://localhost:8080
"""
import sys, io, json, re, socketserver, threading, webbrowser, copy, time, subprocess, shutil
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
PROJECT_DIR = Path(__file__).resolve().parent.parent
USERS_DIR   = PROJECT_DIR / '1_generate_linkedin_cv' / 'users'
USERS_JSON  = PROJECT_DIR / '1_generate_linkedin_cv' / 'users.json'
HTML_PATH   = Path("C:/Users/Leon/Desktop/job_tracker/index.html")
PORT        = 8080
_write_lock      = threading.RLock()   # reentrant: handlers can nest around write_config
ANSI_RE          = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
_search_proc     = None
_search_log      = []
_search_lock     = threading.Lock()
_jobs_cache:       dict[str, list]  = {}
_jobs_cache_mtime: dict[str, float] = {}
_jobs_cache_lock = threading.Lock()

# ── Multi-user state ──────────────────────────────────────────────────────────
_current_user      = 'leon'
_current_user_lock = threading.Lock()

def _user_paths(uid: str) -> dict:
    user_dir = USERS_DIR / uid
    out_dir  = user_dir / 'output'
    return {
        'output_dir':  out_dir,
        'my_cv_dir':   user_dir / 'my_cv',
        'config_path': user_dir / 'config.json',
        'job_summary': out_dir / 'job_summary.md',
    }

def _get_current_uid() -> str:
    with _current_user_lock:
        return _current_user

def _set_current_uid(uid: str):
    global _current_user
    with _current_user_lock:
        _current_user = uid

def _valid_uids() -> list:
    try:
        return [u['id'] for u in json.loads(USERS_JSON.read_text(encoding='utf-8')).get('users', [])]
    except Exception:
        return ['leon']

# ── Location inference from Stepstone URL ─────────────────────────────────────
_CITY_SLUG_MAP = {
    "Hamburg": "Hamburg", "Berlin": "Berlin", "Munich": "Munich",
    "Frankfurt": "Frankfurt", "Lueneburg": "Lüneburg", "Duesseldorf": "Düsseldorf",
    "Essen": "Essen", "Koeln": "Köln", "Muenchen": "München", "Karben": "Karben",
    "Nuernberg": "Nürnberg", "Stuttgart": "Stuttgart", "Cologne": "Köln",
}

def infer_location(job: dict) -> str:
    """Infer city display name from Stepstone URL slug; fallback to location field."""
    url = job.get('url', '') or ''
    if 'stepstone.de' in url:
        for slug, display in _CITY_SLUG_MAP.items():
            if f'-{slug}-' in url:
                return display
    return job.get('location', '') or ''


# ── Parse + merge job data ────────────────────────────────────────────────────
def parse_jobs(uid=None):
    """Parse job_summary.md + jd_analysis.json files.
    Returns cached result when job_summary.md mtime is unchanged."""
    global _jobs_cache, _jobs_cache_mtime
    if uid is None:
        uid = _get_current_uid()
    paths         = _user_paths(uid)
    JOB_SUMMARY_U = paths['job_summary']
    OUTPUT_DIR_U  = paths['output_dir']
    CONFIG_PATH_U = paths['config_path']
    try:
        mtime = JOB_SUMMARY_U.stat().st_mtime if JOB_SUMMARY_U.exists() else 0.0
    except OSError:
        mtime = 0.0
    with _jobs_cache_lock:
        if mtime and mtime == _jobs_cache_mtime.get(uid, 0.0) and _jobs_cache.get(uid):
            return [dict(j) for j in _jobs_cache[uid]]  # per-job copy prevents cross-request mutation

    jobs = []
    header_done = False

    # Build group_id → group_label lookup from config
    cfg = read_config(CONFIG_PATH_U)
    _, kgs, _ = get_keyword_groups(cfg)
    group_label_map = {g.get('group_id',''): g.get('group_label', g.get('group_id','')) for g in kgs}

    with open(JOB_SUMMARY_U, encoding='utf-8') as f:
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
        jd_file = OUTPUT_DIR_U / job['jd_path']
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
            print(f"  WARN {jd_file.name}: {e}", file=sys.stderr)

    # Check if CV + CL materials have been generated
    for job in jobs:
        if not job['jd_path']:
            continue
        job_dir = OUTPUT_DIR_U / Path(job['jd_path']).parent
        job['materials_ready'] = (job_dir / 'cv_final.pdf').exists()

    # ── Load raw (unanalyzed) candidates from temp raw_results files ────────────
    TEMP_DIR = OUTPUT_DIR_U / 'temp'
    analyzed_keys: set[tuple] = set()
    for job in jobs:
        analyzed_keys.add((job['company'].strip().lower(), job['title'].strip().lower()[:60]))

    cfg_for_raw = read_config(CONFIG_PATH_U)
    _, kgs_raw, _ = get_keyword_groups(cfg_for_raw)
    group_label_map_raw = {g.get('group_id', ''): g.get('group_label', g.get('group_id', '')) for g in kgs_raw}

    raw_seen: set[tuple] = set()  # (company, title) already added from raw files

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

    # 更新 mtime 缓存
    with _jobs_cache_lock:
        _jobs_cache[uid] = jobs
        _jobs_cache_mtime[uid] = mtime

    return jobs


# ── Config helpers ────────────────────────────────────────────────────────────
def read_config(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding='utf-8'))

def write_config(data, config_path: Path):
    with _write_lock:
        config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def _set_nested(obj, path_keys, value):
    for k in path_keys[:-1]:
        obj = obj[k]
    obj[path_keys[-1]] = value

def get_keyword_groups(data: dict):
    """Return keyword_groups list from config regardless of nesting."""
    cfg = data
    # Support both top-level and nested under job_search
    if 'keyword_groups' in cfg:
        return cfg, cfg['keyword_groups'], ['keyword_groups']
    js = cfg.get('job_search', {})
    if 'keyword_groups' in js:
        return cfg, js['keyword_groups'], ['job_search', 'keyword_groups']
    return cfg, [], []


# ── Group stats ────────────────────────────────────────────────────────────────
def _load_search_batches(uid=None):
    """Return batches list from search_history.json, or [] if missing/invalid."""
    if uid is None: uid = _get_current_uid()
    history_file = _user_paths(uid)['output_dir'] / 'search_history.json'
    if not history_file.exists():
        return []
    try:
        return json.loads(history_file.read_text(encoding='utf-8')).get('batches', [])
    except Exception:
        return []


def compute_group_stats(uid=None):
    if uid is None: uid = _get_current_uid()
    paths = _user_paths(uid)
    cfg, groups, _ = get_keyword_groups(read_config(paths['config_path']))
    result = []
    now = time.time()
    all_batches = _load_search_batches(uid)

    for grp in groups:
        gid = grp.get('group_id', '')
        prefix = gid + '_'
        folders = [d for d in paths['output_dir'].iterdir()
                   if d.is_dir() and d.name.startswith(prefix)]

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

        # Build search timeline: last 3 batches for this group
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


def compute_search_analysis(uid=None) -> dict:
    """Return per-group keyword search analysis aggregated across ALL batches."""
    if uid is None: uid = _get_current_uid()
    paths = _user_paths(uid)
    history_file = paths['output_dir'] / 'search_history.json'
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

    # ① Aggregate fetched counts across ALL batches
    all_kw_counts: dict[str, int] = {}
    for b in batches:
        for kw, cnt in b.get("fetched_per_keyword", {}).items():
            all_kw_counts[kw] = all_kw_counts.get(kw, 0) + cnt
    print(f"[DEBUG search-analysis] uid={uid} history={history_file} all_kw_counts={dict(list(all_kw_counts.items())[:3])} seen_jobs_len={len(seen_jobs)}", flush=True)

    # ② fallback_triggered = any batch that had this group in groups_with_fallback
    groups_with_fallback: set[str] = set()
    for b in batches:
        for gid in b.get("groups_with_fallback", []):
            groups_with_fallback.add(gid)

    # ③a — Precise match_score from all jd_analysis.json files
    exact_scores: dict[str, float] = {}   # job_id → match_score
    for jd_file in paths['output_dir'].glob("*/jd_analysis.json"):
        try:
            jd = json.loads(jd_file.read_text(encoding='utf-8'))
            jid = str(jd.get("job_id", ""))
            score = jd.get("score") or jd.get("match_score")
            if jid and score is not None:
                exact_scores[jid] = float(score)
        except Exception:
            pass

    # ③b — Per-keyword stats from ALL seen_jobs (exact scores only for analyzed jobs)
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

    # ④ keyword → (group_id, type) purely from config
    cfg, groups_cfg, _ = get_keyword_groups(read_config(paths['config_path']))
    kw_type_map: dict[str, tuple] = {}
    for g in groups_cfg:
        gid = g.get("group_id", "")
        for lang in ("en", "de"):
            for kw in g.get("primary_keywords", {}).get(lang, []):
                kw_type_map.setdefault(kw, (gid, "primary"))
            for kw in g.get("job_family", {}).get(lang, []):
                kw_type_map.setdefault(kw, (gid, "fallback"))

    # Aggregate per group
    group_kw_data: dict[str, list[dict]] = {g["group_id"]: [] for g in groups_cfg}
    for kw, _fetch_count in all_kw_counts.items():
        if ";" in kw:
            first_kw = kw.split(";")[0].strip()
            gid, _ = kw_type_map.get(first_kw, ("", "primary"))
            ktype = "batch"   # always batch so JS filter skips it
            default_src = "stepstone"
        else:
            gid, ktype = kw_type_map.get(kw, ("", "primary"))
            default_src = "linkedin"

        scores_list = kw_exact_scores.get(kw, [])
        sources     = sorted(kw_sources.get(kw, {default_src}))
        distinct    = kw_distinct.get(kw, _fetch_count)
        high     = sum(1 for s in scores_list if s >= 70)
        good     = sum(1 for s in scores_list if 50 <= s < 70)
        moderate = sum(1 for s in scores_list if 30 <= s < 50)

        if gid in group_kw_data:
            group_kw_data[gid].append({
                "keyword":   kw,
                "type":      ktype,
                "sources":   sources,
                "count":     distinct,          # all found jobs (from seen_jobs)
                "analyzed":  len(scores_list),  # how many have been precisely analyzed
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
_SEARCH_MAX_S = 1800  # 30 分钟硬上限，防 claude 进程无限挂起

def _run_search(cmd):
    global _search_proc, _search_log
    claude_bin = shutil.which('claude') or 'claude'
    with _search_lock:
        _search_log = []
        _search_proc = subprocess.Popen(
            [claude_bin, '-p', cmd],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=str(PROJECT_DIR), text=True,
            encoding='utf-8', errors='replace',
        )

    # Watchdog：超时后强制 kill，防止 MCP 挂起导致线程永久占用
    def _watchdog(proc):
        time.sleep(_SEARCH_MAX_S)
        if proc and proc.poll() is None:
            proc.kill()
            _search_log.append('[TIMEOUT] Search process killed after 30 min')
    threading.Thread(target=_watchdog, args=(_search_proc,), daemon=True).start()

    try:
        for line in _search_proc.stdout:
            stripped = ANSI_RE.sub('', line.rstrip())
            if stripped and len(_search_log) < 5000:
                _search_log.append(stripped)
    finally:
        _search_proc.wait()


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
        uid  = _get_current_uid()

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
                summary = _user_paths(uid)['job_summary']
                mtime = summary.stat().st_mtime if summary.exists() else 0.0
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
                cv_dir = _user_paths(uid)['my_cv_dir']
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
                fpath = _user_paths(uid)['my_cv_dir'] / name
                if not fpath.exists() or not fpath.is_file():
                    self._send(b'Not found', 'text/plain', 404)
                    return
                self._send(fpath.read_bytes(), 'application/pdf')
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/users':
            try:
                data = json.loads(USERS_JSON.read_text(encoding='utf-8'))
                data['current'] = uid
                self._send(json.dumps(data, ensure_ascii=False))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/taxonomy':
            try:
                cfg = read_config(_user_paths(uid)['config_path'])
                self._send(json.dumps(cfg.get('skill_taxonomy') or {}, ensure_ascii=False))
            except Exception:
                self._send(json.dumps({}))

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
            deadline = time.monotonic() + _SEARCH_MAX_S + 60  # 略大于 watchdog 上限
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
                    # deadline reached — watchdog已kill进程，通知前端
                    self.wfile.write(b'data: {"timeout":true}\n\n')
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        else:
            self._send(b'Not found', 'text/plain', 404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == '/api/record':
            try:
                data = self._read_json_body()
                result, status = _update_jd_field(data.get('jd_path'), 'application_record', data.get('record'))
                self._send(json.dumps(result), status=status)
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)
        elif path == '/api/note':
            try:
                data = self._read_json_body()
                result, status = _update_jd_field(data.get('jd_path'), 'user_note', data.get('note', ''))
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
                uid = _get_current_uid()
                cfg_path = _user_paths(uid)['config_path']
                with _write_lock:
                    cfg, groups, path_keys = get_keyword_groups(read_config(cfg_path))
                    new_groups = [g for g in groups if g.get('group_id') != gid]
                    if len(new_groups) == len(groups):
                        self._send(json.dumps({'error': f'group_id not found: {gid}'}), status=404)
                        return
                    _set_nested(cfg, path_keys, new_groups)
                    write_config(cfg, cfg_path)
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
                uid = _get_current_uid()
                cfg_path = _user_paths(uid)['config_path']
                with _write_lock:
                    cfg, groups, path_keys = get_keyword_groups(read_config(cfg_path))
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
                    write_config(cfg, cfg_path)
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
                uid = _get_current_uid()
                cfg_path = _user_paths(uid)['config_path']
                with _write_lock:
                    cfg, groups, path_keys = get_keyword_groups(read_config(cfg_path))
                    if any(g.get('group_id') == gid for g in groups):
                        self._send(json.dumps({'error': f'group_id already exists: {gid}'}), status=409)
                        return
                    groups.append(grp)
                    _set_nested(cfg, path_keys, groups)
                    write_config(cfg, cfg_path)
                self._send(json.dumps({'ok': True, 'group_id': gid}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/search':
            try:
                data = self._read_json_body()
                group_id = data.get('group_id', 'all')
                uid = _get_current_uid()
                cfg = read_config(_user_paths(uid)['config_path'])
                _, kgs, _ = get_keyword_groups(cfg)
                valid_ids = {g.get('group_id') for g in kgs}
                if group_id != 'all' and group_id not in valid_ids:
                    self._send(json.dumps({'error': 'invalid group_id'}), status=400)
                    return
                with _search_lock:
                    if _search_proc and _search_proc.poll() is None:
                        self._send(json.dumps({'error': 'search already running'}), status=409)
                        return
                cmd = f'搜索职缺 {group_id}' if group_id != 'all' else '搜索职缺'
                threading.Thread(target=_run_search, args=(cmd,), daemon=True).start()
                self._send(json.dumps({'ok': True, 'cmd': cmd}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/switch-user':
            try:
                data    = self._read_json_body()
                new_uid = (data.get('user_id') or '').strip()
                valid   = _valid_uids()
                if new_uid not in valid:
                    self._send(json.dumps({'error': 'unknown user'}), status=400)
                    return
                with _search_lock:
                    if _search_proc and _search_proc.poll() is None:
                        self._send(json.dumps({'error': 'search_running'}), status=409)
                        return
                    _set_current_uid(new_uid)   # inside lock: atomic check-then-switch
                with _jobs_cache_lock:
                    _jobs_cache_mtime[new_uid] = 0.0
                self._send(json.dumps({'ok': True}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path == '/api/create-user':
            try:
                data = self._read_json_body()
                uid  = (data.get('user_id') or '').strip().lower()
                name = (data.get('name') or '').strip()
                if not uid or not name:
                    self._send(json.dumps({'error': 'user_id and name required'}), status=400)
                    return
                if not uid.replace('-', '').isalnum():
                    self._send(json.dumps({'error': 'user_id must be alphanumeric'}), status=400)
                    return
                users_data = json.loads(USERS_JSON.read_text(encoding='utf-8'))
                if any(u['id'] == uid for u in users_data.get('users', [])):
                    self._send(json.dumps({'error': f'user already exists: {uid}'}), status=409)
                    return
                users_data.setdefault('users', []).append({'id': uid, 'name': name})
                with _write_lock:
                    USERS_JSON.write_text(json.dumps(users_data, ensure_ascii=False, indent=2), encoding='utf-8')
                user_dir = USERS_DIR / uid
                (user_dir / 'output' / 'temp').mkdir(parents=True, exist_ok=True)
                (user_dir / 'my_cv').mkdir(parents=True, exist_ok=True)
                self._send(json.dumps({'ok': True}))
            except Exception as e:
                self._send(json.dumps({'error': str(e)}), status=500)

        elif path in ('/api/generate-job-family', '/api/save-job-family'):
            self._send(json.dumps({'error': 'not implemented'}), status=501)

        else:
            self._send(json.dumps({'error': 'Not found'}), status=404)

    def log_message(self, fmt, *args):
        if args and str(args[1]) not in ('200', '204', '304'):
            print(f"  {self.address_string()} {fmt % args}", file=sys.stderr)


# ── JD file helpers ──────────────────────────────────────────────────────────
def _update_jd_field(jd_path: str, field: str, value, uid=None):
    """Read jd_analysis.json, set one field, write back. Returns (dict, http_status)."""
    if not jd_path or '..' in jd_path:
        return {'error': f'{field} requires valid jd_path'}, 400
    if uid is None: uid = _get_current_uid()
    jd_file = _user_paths(uid)['output_dir'] / jd_path
    if not jd_file.exists():
        return {'error': f'File not found: {jd_path}'}, 404
    with _write_lock:
        detail = json.loads(jd_file.read_text(encoding='utf-8'))
        detail[field] = value
        jd_file.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding='utf-8')
    with _jobs_cache_lock:
        _jobs_cache_mtime[uid] = 0.0
    return {'ok': True}, 200


# ── Threading server ──────────────────────────────────────────────────────────
class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # 首次启动时若 index.html 不存在则自动生成
    if not HTML_PATH.exists():
        print(f'Generating {HTML_PATH} …')
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
    print(f'Users: {USERS_DIR}')
    print('Ctrl+C to stop.\n')
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped.')
