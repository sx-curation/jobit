#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server_search.py — Search subprocess management extracted from server.py (Week 3/4 split).

Contains: search process lifecycle, SSE log buffer, subprocess watchdog,
          and HTTP route handlers for search endpoints.

Routes handled:
  GET  /api/search-status
  GET  /api/search-log  (SSE, ?group_id=xxx)
  GET  /api/health
  POST /api/search
"""
import json
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from server_jobs import _user_dir, read_config, get_keyword_groups  # noqa: E402

# ── Shared ANSI stripper ──────────────────────────────────────────────────────
ANSI_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# ── Search state ──────────────────────────────────────────────────────────────
_SEARCH_MAX_S   = 1800   # 30-minute hard limit
MAX_CONCURRENT  = 2      # max simultaneous group searches

# Key = "{uid}:{group_id}"  (group_id may be "all")
_search_procs: dict = {}   # key → Popen
_search_logs:  dict = {}   # key → list[str]
_search_lock        = threading.Lock()


# ── State helpers ─────────────────────────────────────────────────────────────

def _make_key(uid: str, group_id: str) -> str:
    return f"{uid}:{group_id}"


def get_running_searches() -> list:
    """Return list of currently-running search dicts: {key, uid, group_id}."""
    result = []
    for key, proc in list(_search_procs.items()):
        if proc.poll() is None:
            uid, group_id = key.split(':', 1)
            result.append({'key': key, 'uid': uid, 'group_id': group_id})
    return result


def is_search_running() -> bool:
    """True if any search is currently running (backward compat)."""
    return len(get_running_searches()) > 0


def _is_key_running(key: str) -> bool:
    proc = _search_procs.get(key)
    return proc is not None and proc.poll() is None


def get_search_logs(key: str) -> list:
    """Return the log buffer for the given search key."""
    return _search_logs.get(key, [])


def kill_search() -> bool:
    """Kill all running search processes. Returns True if anything was killed."""
    killed = False
    for proc in _search_procs.values():
        if proc.poll() is None:
            proc.kill()
            killed = True
    return killed


# ── Batch history ─────────────────────────────────────────────────────────────
_BATCH_LOG = 'output/temp/_search_batch_log.json'

def _batch_record(user_dir: Path, group_id: str, event: str, **kw):
    """Append start record or update latest running record with end info."""
    path = user_dir / _BATCH_LOG
    try:
        records = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    except Exception:
        records = []
    if event == 'start':
        records.append({'group_id': group_id,
                        'started': datetime.now(timezone.utc).isoformat(),
                        'status': 'running'})
        records = records[-30:]
    elif event == 'end':
        for r in reversed(records):
            if r.get('group_id') == group_id and r.get('status') == 'running':
                r.update(finished=datetime.now(timezone.utc).isoformat(), **kw)
                break
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass


def _resolve_group_id(b: dict, user_dir: Path) -> str | None:
    """Read first job's _group_id from a batch's raw_results file."""
    raw_file_val = b.get('raw_results_file', '')
    for candidate in [Path(raw_file_val), user_dir / raw_file_val]:
        try:
            if candidate.exists():
                jobs = json.loads(candidate.read_text(encoding='utf-8'))
                return jobs[0].get('_group_id') if jobs else None
        except Exception:
            pass
    return None


def _find_orphaned_folders(uid: str, group_id: str) -> list:
    """Return output folders that have jd_text.txt but no jd_analysis.json."""
    out_dir = _user_dir(uid) / 'output'
    result = []
    try:
        prefix = group_id + '_'
        for sub in out_dir.iterdir():
            if sub.is_dir() and sub.name.startswith(prefix):
                if (sub / 'jd_text.txt').exists() and not (sub / 'jd_analysis.json').exists():
                    result.append(sub)
    except Exception:
        pass
    return result


def _get_batch_stats(uid: str) -> dict:
    """Return live stats for the search log drawer."""
    user_dir = _user_dir(uid)
    out_dir  = user_dir / 'output'

    # search_history.json
    recent_batches: list = []
    batches: list = []
    try:
        hist = json.loads((out_dir / 'search_history.json').read_text(encoding='utf-8'))
        batches = hist.get('batches', [])
        recent_batches = batches[-5:]
    except Exception:
        pass

    # Collect up to 5 pending batches from the last 30 days
    cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
    pending_batches: list = []
    for b in reversed(batches):
        if b.get('batch_id', '') < cutoff:
            break
        if not b.get('dedup_done') or b.get('new_total') is None \
                or b.get('skipped_analysis', 0) > 0:
            group_id = _resolve_group_id(b, user_dir)
            if not group_id:
                continue  # raw_results gone; skip stale entry
            fetched_actual = sum(b.get('fetched_per_source', {}).values()) or b.get('fetched_total', 0)
            pending_batches.append({
                'batch_id':         b.get('batch_id'),
                'date':             b.get('date'),
                'fetched_actual':   fetched_actual,
                'new_total':        b.get('new_total'),
                'skipped_duplicate': b.get('skipped_duplicate', 0),
                'skipped_analysis': b.get('skipped_analysis', 0),
                'dedup_done':       b.get('dedup_done'),
                'group_id':         group_id,
            })
            if len(pending_batches) >= 5:
                break

    # Detect orphaned job folders: jd_text.txt exists but jd_analysis.json absent.
    # These indicate an interrupted Phase 2E and need a re-run of analysis only.
    try:
        orphaned_by_group: dict[str, list[str]] = {}
        for sub in out_dir.iterdir():
            if not sub.is_dir():
                continue
            parts = sub.name.split('_')
            if len(parts) < 2 or not parts[0].startswith('group-'):
                continue
            if (sub / 'jd_text.txt').exists() and not (sub / 'jd_analysis.json').exists():
                orphaned_by_group.setdefault(parts[0], []).append(sub.name)
        for grp, folders in orphaned_by_group.items():
            if len(pending_batches) >= 5:
                break
            if any(pb.get('group_id') == grp for pb in pending_batches):
                continue  # already represented
            dates = [f.rsplit('_', 1)[-1] for f in folders
                     if len(f.rsplit('_', 1)[-1]) == 8 and f.rsplit('_', 1)[-1].isdigit()]
            batch_date = max(dates) if dates else None
            pending_batches.insert(0, {
                'batch_id':          batch_date,
                'date':              (f"{batch_date[:4]}-{batch_date[4:6]}-{batch_date[6:]}"
                                      if batch_date else None),
                'fetched_actual':    len(folders),
                'new_total':         None,
                'skipped_duplicate': 0,
                'skipped_analysis':  len(folders),
                'dedup_done':        True,
                'group_id':          grp,
            })
    except Exception:
        pass

    # backward-compat single-batch fields
    pending_batch    = pending_batches[0] if pending_batches else None
    pending_group_id = pending_batch['group_id'] if pending_batch else None

    # running search
    running = get_running_searches()
    active  = running[-1] if running else None
    active_gid = active['group_id'] if active else None
    active_key = active['key'] if active else None

    # parse in-memory log for phase/progress
    phase      = 'idle'
    cumulative = 0
    current_kw = ''
    high_score = None
    log_lines  = _search_logs.get(active_key, []) if active_key else []
    is_running = _is_key_running(active_key) if active_key else False

    if active_key:
        if not log_lines:
            phase = 'starting'
        else:
            for line in reversed(log_lines):
                m = re.search(r'cumulative=\s*(\d+)', line)
                if m:
                    cumulative = int(m.group(1))
                    km = re.search(r"kw='([^']+)'", line)
                    current_kw = km.group(1) if km else ''
                    phase = 'scraping'
                    break
            if phase == 'idle':
                phase = 'analyzing'
            for line in log_lines:
                m = re.search(r':\s*(\d+)\s+jobs with score\s*>', line)
                if m:
                    high_score = int(m.group(1))

    if not is_running and pending_batches:
        phase = 'pending_analysis'
    elif not is_running and active_key:
        phase = 'completed'

    # count analyzed output dirs for active/first-pending group
    analyzed_today = 0
    total_analyzed = 0
    gid_for_count  = active_gid or pending_group_id
    if not gid_for_count and batches:
        gid_for_count = _resolve_group_id(batches[-1], user_dir)
    if gid_for_count:
        today_str = datetime.now().strftime('%Y%m%d')
        for d in out_dir.iterdir():
            if d.is_dir() and d.name.startswith(gid_for_count):
                total_analyzed += 1
                if today_str in d.name:
                    analyzed_today += 1

    return {
        'running':          is_running,
        'active_group_id':  active_gid,
        'phase':            phase,
        'cumulative':       cumulative,
        'current_kw':       current_kw,
        'high_score':       high_score,
        'analyzed_today':   analyzed_today,
        'total_analyzed':   total_analyzed,
        'pending_batch':    pending_batch,
        'pending_group_id': pending_group_id,
        'pending_batches':  pending_batches,
        'recent_batches':   recent_batches,
    }


# ── Search runner ─────────────────────────────────────────────────────────────

def _run_search(cmd: str, uid: str, group_id: str, user_dir: Path):
    """
    Spawn `claude --dangerously-skip-permissions -p <cmd>` in user_dir.
    Streams stdout into _search_logs[key]. Kills after _SEARCH_MAX_S.
    """
    key        = _make_key(uid, group_id)
    claude_bin = shutil.which('claude') or 'claude'

    with _search_lock:
        _search_logs[key] = []
        _search_procs[key] = subprocess.Popen(
            [claude_bin, '--dangerously-skip-permissions', '-p', cmd],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=str(user_dir), text=True,
            encoding='utf-8', errors='replace',
        )

    log  = _search_logs[key]
    proc = _search_procs[key]

    _batch_record(user_dir, group_id, 'start')

    def _watchdog():
        time.sleep(_SEARCH_MAX_S)
        if proc.poll() is None:
            proc.kill()
            log.append('[TIMEOUT] Search process killed after 30 min')
    threading.Thread(target=_watchdog, daemon=True).start()

    try:
        for line in proc.stdout:
            stripped = ANSI_RE.sub('', line.rstrip())
            if stripped and len(log) < 5000:
                log.append(stripped)
    finally:
        proc.wait()
        timed_out = any('[TIMEOUT]' in l for l in log[-5:])
        status = 'timeout' if timed_out else ('completed' if proc.returncode == 0 else 'interrupted')
        _batch_record(user_dir, group_id, 'end', status=status)


# ── Route handlers ─────────────────────────────────────────────────────────────

def handle_get(path: str, qs: dict, uid: str, h) -> bool:
    """Handle GET; return True if handled."""

    if path == '/api/batch-stats':
        h._send(json.dumps(_get_batch_stats(uid)))
        return True

    if path == '/api/search-status':
        searches = get_running_searches()
        h._send(json.dumps({'running': len(searches) > 0, 'searches': searches}))
        return True

    elif path == '/api/search-log':
        h.send_response(200)
        h.send_header('Content-Type', 'text/event-stream')
        h.send_header('Cache-Control', 'no-cache')
        h.send_header('Access-Control-Allow-Origin', '*')
        h.end_headers()

        group_id = qs.get('group_id', [None])[0]
        if group_id:
            key = _make_key(uid, group_id)
        else:
            running = [r for r in get_running_searches() if r['uid'] == uid]
            if not running:
                running = get_running_searches()
            key = running[-1]['key'] if running else _make_key(uid, 'all')

        progress_log = _user_dir(uid) / 'output' / 'temp' / '_search_progress.log'

        def _emit(text: str):
            data = json.dumps({'text': text}, ensure_ascii=False)
            h.wfile.write(f'data: {data}\n\n'.encode('utf-8'))
            h.wfile.flush()

        # ── Initial context: last 50 lines from progress file ─────────────────
        file_pos = 0
        try:
            if progress_log.exists():
                raw = progress_log.read_bytes()
                for line in raw.decode('utf-8', errors='replace').splitlines()[-50:]:
                    if line.strip():
                        _emit(line)
                file_pos = len(raw)
        except Exception:
            pass

        sent_mem   = 0
        file_quiet = 0    # ticks since progress file last grew (0.3 s each)
        deadline   = time.monotonic() + _SEARCH_MAX_S + 60

        try:
            while time.monotonic() < deadline:
                # ── Memory buffer (Claude stdout) ─────────────────────────────
                log = _search_logs.get(key, [])
                if sent_mem > len(log):   # new run replaced the list
                    sent_mem = 0
                while sent_mem < len(log):
                    _emit(log[sent_mem]); sent_mem += 1

                # ── Progress file (search scripts write directly) ─────────────
                try:
                    if progress_log.exists():
                        sz = progress_log.stat().st_size
                        if sz > file_pos:
                            with open(progress_log, 'rb') as f:
                                f.seek(file_pos)
                                new_raw = f.read()
                            file_pos += len(new_raw)
                            file_quiet = 0          # file still being written
                            for line in new_raw.decode('utf-8', errors='replace').splitlines():
                                if line.strip():
                                    _emit(line)
                        else:
                            file_quiet += 1
                    else:
                        file_quiet += 1
                except Exception:
                    file_quiet += 1

                # ── Done: process stopped AND file quiet for ≥10 s ───────────
                log = _search_logs.get(key, [])
                if not _is_key_running(key) and file_quiet >= 33 and sent_mem >= len(log):
                    h.wfile.write(b'data: {"done":true}\n\n')
                    h.wfile.flush()
                    break

                time.sleep(0.3)
            else:
                h.wfile.write(b'data: {"timeout":true}\n\n')
                h.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        return True

    elif path == '/api/search-history':
        hist_path = _user_dir(uid) / _BATCH_LOG
        try:
            records = json.loads(hist_path.read_text(encoding='utf-8')) if hist_path.exists() else []
        except Exception:
            records = []
        h._send(json.dumps(records[-10:]))
        return True

    if path == '/api/health':
        claude_ok = bool(shutil.which('claude'))
        h._send(json.dumps({'claude': claude_ok}))
        return True

    return False


def _validate_config(cfg: dict, uid: str) -> list:
    errors = []
    _, kgs, _ = get_keyword_groups(cfg, uid)
    if not kgs:
        errors.append("config.json 中未找到 keyword_groups，请在 My CVs > Groups 创建至少一个 Group")
        return errors
    user_dir = _user_dir(uid)
    for g in kgs:
        gid     = g.get('group_id', '(unnamed)')
        cv_file = g.get('cv_file', '')
        if not cv_file:
            errors.append(f"Group '{gid}': 缺少 cv_file 字段")
        elif not (user_dir / cv_file).exists():
            errors.append(f"Group '{gid}': cv_file '{cv_file}' 不存在")
        kws = g.get('primary_keywords', {})
        if not kws.get('en') and not kws.get('de'):
            errors.append(f"Group '{gid}': primary_keywords 中 en 和 de 均为空")
    return errors


def handle_post(path: str, qs: dict, uid: str, h) -> bool:
    """Handle POST; return True if handled."""

    if path == '/api/search':
        try:
            data     = h._read_json_body()
            group_id = data.get('group_id', 'all')
            cfg      = read_config(uid)
            _, kgs, _ = get_keyword_groups(cfg, uid)
            valid_ids = {g.get('group_id') for g in kgs}
            if group_id != 'all' and group_id not in valid_ids:
                h._send(json.dumps({'error': 'invalid group_id'}), status=400); return True
            errs = _validate_config(cfg, uid)
            if errs:
                h._send(json.dumps({'error': 'Config validation failed', 'details': errs}), status=400); return True

            with _search_lock:
                key     = _make_key(uid, group_id)
                running = get_running_searches()
                if _is_key_running(key):
                    h._send(json.dumps({'error': '该 group 已在搜索中', 'searches': running}), status=409)
                    return True
                if len(running) >= MAX_CONCURRENT:
                    h._send(json.dumps({
                        'error': f'最多允许 {MAX_CONCURRENT} 组同时搜索',
                        'searches': running,
                    }), status=429)
                    return True

            action   = data.get('action', 'search')
            orphaned = _find_orphaned_folders(uid, group_id) if action == 'analyze' else []
            cmd = f'精确分析 {group_id}' if orphaned else (
                f'搜索职缺 {group_id}' if group_id != 'all' else '搜索职缺'
            )
            threading.Thread(
                target=_run_search, args=(cmd, uid, group_id, _user_dir(uid)), daemon=True
            ).start()
            h._send(json.dumps({'ok': True, 'cmd': cmd, 'group_id': group_id}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    return False
