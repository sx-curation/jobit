#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Job Tracker local server — stdlib only, no pip installs required.
Run:  python scripts/server.py
Opens: http://localhost:8080
'''
import io, json, socketserver, sys, threading, webbrowser
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── Sub-modules (Week 3/4 split) ──────────────────────────────────────────────
import server_jobs   as _sj
import server_search as _ss
import server_ai     as _sa
import server_users  as _su

# Re-export so existing callers (tests, scripts) continue to work via `server.*`
from server_jobs import (        # noqa: F401
    infer_location, _to_str_list, _parse_relative_date, _get_job_level,
    read_config, _load_taxonomy, write_config, _set_nested, get_keyword_groups,
    parse_jobs, _load_search_batches, compute_group_stats, compute_search_analysis,
    compute_group_skill_gaps, _update_jd_field,
    _jobs_cache, _jobs_cache_mtime, _jobs_cache_lock,
)
from server_ai    import _extract_qa, _build_form_fields       # noqa: F401
from server_users import (                                      # noqa: F401
    _load_users, _register_user, _run_generate_job_family,
    _cur_uid, set_current_user,
)

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
USERS_DIR   = PROJECT_DIR / 'users'
USERS_JSON  = PROJECT_DIR / 'users.json'
HTML_PATH   = PROJECT_DIR / 'dashboard' / 'index.html'
PORT        = 8080


def _user_dir(uid: str) -> Path: return USERS_DIR / uid
def get_output_dir(uid: str) -> Path: return _user_dir(uid) / 'output'
def get_cv_dir(uid: str)     -> Path: return _user_dir(uid) / 'my_cv'
def get_config_path(uid: str)-> Path: return _user_dir(uid) / 'config.json'
def get_job_summary(uid: str)-> Path: return get_output_dir(uid) / 'job_summary.md'


def _run_search(cmd: str, uid: str, group_id: str = 'all'):
    """Thin wrapper — resolves user_dir before delegating to server_search."""
    _ss._run_search(cmd, uid, group_id, _user_dir(uid))


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
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)
        uid    = qs.get('uid', [None])[0] or _cur_uid()

        # Static files — handled directly, no uid needed
        if path in ('/', '/index.html'):
            if HTML_PATH.exists():
                body = HTML_PATH.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
            else:
                self._send(
                    b'<h2>index.html not found.<br>Run: python scripts/gen_job_tracker_html.py</h2>',
                    'text/html', 404,
                )
            return

        if path == '/logo.png':
            logo = PROJECT_DIR / 'dashboard' / 'logo.png'
            if logo.exists():
                self._send(logo.read_bytes(), 'image/png')
            else:
                self._send(b'Not found', 'text/plain', 404)
            return

        # Route dispatch
        if   _sj.handle_get(path, qs, uid, self): return
        elif _ss.handle_get(path, qs, uid, self): return
        elif _sa.handle_get(path, qs, uid, self): return
        elif _su.handle_get(path, qs, uid, self): return
        else:
            self._send(b'Not found', 'text/plain', 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path
        qs     = parse_qs(parsed.query)
        uid    = qs.get('uid', [None])[0] or _cur_uid()

        if   _sj.handle_post(path, qs, uid, self): return
        elif _ss.handle_post(path, qs, uid, self): return
        elif _sa.handle_post(path, qs, uid, self): return
        elif _su.handle_post(path, qs, uid, self): return
        else:
            self._send(json.dumps({'error': 'Not found'}), status=404)

    def log_message(self, fmt, *args):
        if args and str(args[1]) not in ('200', '204', '304'):
            print(f'  {self.address_string()} {fmt % args}', file=sys.stderr)


# ── Threading server ──────────────────────────────────────────────────────────
class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    if USERS_JSON.exists():
        try:
            registry = json.loads(USERS_JSON.read_text(encoding='utf-8'))
            if registry.get('users'):
                set_current_user(registry['users'][0]['id'])
        except Exception:
            pass

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
