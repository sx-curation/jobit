#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server_users.py — User registry, current-user state, group CRUD, and LLM job-family
generation extracted from server.py (Week 3/4 split).

Contains:
  _current_user / _cur_uid / set_current_user  — server-wide default uid (P0 fix)
  _load_users / _register_user                  — users.json CRUD
  _run_generate_job_family                      — LLM keyword expansion
  handle_get / handle_post                      — HTTP routes for:
    GET  /api/users
    POST /api/switch-user, /api/create-user,
         /api/generate-job-family, /api/save-job-family,
         /api/group-delete, /api/group-dup, /api/group-save
"""
import copy
import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
USERS_DIR   = PROJECT_DIR / 'users'
USERS_JSON  = PROJECT_DIR / 'users.json'

ANSI_RE     = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
_write_lock = threading.Lock()   # guards users.json writes

_MODEL_CFG: dict | None = None

def _get_server_model(key: str) -> str:
    """Read model ID from config/model_config.json (lazy-loaded, cached)."""
    global _MODEL_CFG
    if _MODEL_CFG is None:
        try:
            _MODEL_CFG = json.loads(
                (PROJECT_DIR / 'config' / 'model_config.json').read_text(encoding='utf-8')
            )
        except Exception:
            _MODEL_CFG = {}
    return _MODEL_CFG.get('server_endpoints', {}).get(key, 'claude-haiku-4-5')


# ── Current-user global (P0) ──────────────────────────────────────────────────
# This is the fallback uid used when a request arrives without an explicit ?uid=.
# The dashboard should pass ?uid= on every API call; _cur_uid() is a last resort.
# WARNING in stderr is emitted by server.py's dispatcher when the fallback fires.
def _load_default_user() -> str:
    try:
        data = json.loads(USERS_JSON.read_text(encoding='utf-8'))
        return data['users'][0]['id']
    except Exception:
        return 'leon'

_current_user = _load_default_user()
_user_lock    = threading.Lock()


def _cur_uid() -> str:
    with _user_lock:
        return _current_user


def set_current_user(uid: str) -> None:
    global _current_user
    with _user_lock:
        _current_user = uid


# ── Users registry ────────────────────────────────────────────────────────────
def _load_users() -> dict:
    """Read users.json; return {"users": []} if missing/invalid."""
    if not USERS_JSON.exists():
        return {"users": []}
    try:
        return json.loads(USERS_JSON.read_text(encoding='utf-8'))
    except Exception:
        return {"users": []}


def _register_user(uid: str, name: str):
    """Append user to users.json (write-lock protected)."""
    with _write_lock:
        registry = _load_users()
        if any(u['id'] == uid for u in registry['users']):
            return
        registry['users'].append({'id': uid, 'name': name})
        USERS_JSON.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2), encoding='utf-8'
        )


# ── LLM job-family generation ─────────────────────────────────────────────────
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
    """Returns (result_dict, None) or (None, error_dict). Blocking ~15s."""
    prompt = _build_job_family_prompt(group)
    claude_bin = shutil.which('claude') or 'claude'
    model = _get_server_model('generate_job_family')
    try:
        proc = subprocess.run(
            [claude_bin, '-p', prompt, '--model', model],
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


# ── Route handlers ────────────────────────────────────────────────────────────
# server_jobs is imported here (not circular: server_jobs does not import server_users).
import server_jobs as _sj  # noqa: E402


def handle_get(path: str, qs: dict, uid: str, h) -> bool:
    """Handle GET; return True if handled."""
    if path == '/api/users':
        try:
            registry = _load_users()
            h._send(json.dumps({
                'current': uid,
                'users': registry.get('users', [])
            }, ensure_ascii=False))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/preferences':
        try:
            cfg  = _sj.read_config(uid)
            js   = cfg.get('job_search', {})
            pref = cfg.get('preferences', {})
            h._send(json.dumps({
                'preferred_locations':            pref.get('preferred_locations', []),
                'preferred_work_mode':            pref.get('preferred_work_mode', []),
                'salary_expectation_eur_monthly': pref.get('salary_expectation_eur_monthly', 0),
                'preferred_domains':              pref.get('preferred_domains', []),
                'preferred_level':                pref.get('preferred_level', ''),
                'language_skills':                pref.get('language_skills', []),
                'stepstone_enabled':              cfg.get('stepstone', {}).get('enabled', False),
                'auto_default_answers':           cfg.get('auto_default_answers', True),
                'date_range_days':                js.get('date_range_days', 14),
                'max_display':                    js.get('max_display', 30),
            }, ensure_ascii=False))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    return False


def handle_post(path: str, qs: dict, uid: str, h) -> bool:
    """Handle POST; return True if handled."""

    if path == '/api/switch-user':
        try:
            data    = h._read_json_body()
            new_uid = (data.get('user_id') or '').strip()
            if not new_uid:
                h._send(json.dumps({'error': 'user_id required'}), status=400); return True
            import server_search as _ss  # noqa: PLC0415
            with _ss._search_lock:
                if _ss.is_search_running():
                    h._send(json.dumps({'error': 'search_running'}), status=409); return True
            if not (USERS_DIR / new_uid).is_dir():
                h._send(json.dumps({'error': f'user not found: {new_uid}'}), status=404); return True
            set_current_user(new_uid)
            h._send(json.dumps({'ok': True, 'user_id': new_uid}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/create-user':
        try:
            data    = h._read_json_body()
            name    = (data.get('name') or '').strip()
            new_uid = (data.get('user_id') or '').strip()
            if not name or not new_uid:
                h._send(json.dumps({'error': 'name and user_id required'}), status=400); return True
            if re.search(r'[^a-z0-9\-_]', new_uid):
                h._send(json.dumps({'error': 'user_id must be lowercase alphanumeric'}), status=400); return True
            if (USERS_DIR / new_uid).exists():
                h._send(json.dumps({'error': f'user already exists: {new_uid}'}), status=409); return True
            user_dir = USERS_DIR / new_uid
            (user_dir / 'output' / 'temp').mkdir(parents=True, exist_ok=True)
            (user_dir / 'my_cv').mkdir(exist_ok=True)
            (user_dir / 'memory').mkdir(exist_ok=True)
            for jname in ['.claude', 'scripts', 'graphify-out']:
                link   = user_dir / jname
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
                template = {"job_search": {"keyword_groups": []}, "skill_taxonomy": {}, "auto_default_answers": True}
                cfg_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding='utf-8')
            _register_user(new_uid, name)
            h._send(json.dumps({'ok': True, 'user_id': new_uid}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/generate-job-family':
        try:
            data = h._read_json_body()
            gid  = (data.get('group_id') or '').strip()
            cfg, groups, _ = _sj.get_keyword_groups(uid=uid)
            target = next((g for g in groups if g.get('group_id') == gid), None)
            if not target:
                h._send(json.dumps({'error': f'group not found: {gid}'}), status=404); return True
            result, err = _run_generate_job_family(target)
            if err:
                h._send(json.dumps({'error': err['message'], 'raw': err.get('raw', '')}), status=500)
            else:
                h._send(json.dumps({'ok': True, 'result': result}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/save-job-family':
        try:
            data = h._read_json_body()
            gid  = (data.get('group_id') or '').strip()
            jf   = data.get('job_family')
            if not gid or jf is None:
                h._send(json.dumps({'error': 'group_id and job_family required'}), status=400); return True
            cfg, groups, path_keys = _sj.get_keyword_groups(uid=uid)
            target = next((g for g in groups if g.get('group_id') == gid), None)
            if not target:
                h._send(json.dumps({'error': f'group not found: {gid}'}), status=404); return True
            target['job_family'] = jf
            _sj._set_nested(cfg, path_keys, groups)
            _sj.write_config(cfg, uid)
            h._send(json.dumps({'ok': True}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/group-delete':
        try:
            data = h._read_json_body()
            gid  = data.get('group_id', '').strip()
            if not gid:
                h._send(json.dumps({'error': 'group_id required'}), status=400); return True
            cfg, groups, path_keys = _sj.get_keyword_groups(uid=uid)
            new_groups = [g for g in groups if g.get('group_id') != gid]
            if len(new_groups) == len(groups):
                h._send(json.dumps({'error': f'group_id not found: {gid}'}), status=404); return True
            _sj._set_nested(cfg, path_keys, new_groups)
            _sj.write_config(cfg, uid)
            h._send(json.dumps({'ok': True}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/group-dup':
        try:
            data = h._read_json_body()
            gid  = data.get('group_id', '').strip()
            if not gid:
                h._send(json.dumps({'error': 'group_id required'}), status=400); return True
            cfg, groups, path_keys = _sj.get_keyword_groups(uid=uid)
            originals = [g for g in groups if g.get('group_id') == gid]
            if not originals:
                h._send(json.dumps({'error': f'group_id not found: {gid}'}), status=404); return True
            new_grp = copy.deepcopy(originals[0])
            taken   = {g.get('group_id', '') for g in groups}
            base    = gid + '-copy'
            new_id  = base
            i = 2
            while new_id in taken:
                new_id = f'{base}-{i}'; i += 1
            new_grp['group_id']    = new_id
            new_grp['group_label'] = new_grp.get('group_label', gid) + ' (Copy)'
            groups.append(new_grp)
            _sj._set_nested(cfg, path_keys, groups)
            _sj.write_config(cfg, uid)
            h._send(json.dumps({'ok': True, 'new_group_id': new_id}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/group-save':
        try:
            data = h._read_json_body()
            grp  = data.get('group')
            if not grp or not grp.get('group_id'):
                h._send(json.dumps({'error': 'group_id required'}), status=400); return True
            gid = grp['group_id'].strip()
            if not gid:
                h._send(json.dumps({'error': 'group_id must not be empty'}), status=400); return True
            cfg, groups, path_keys = _sj.get_keyword_groups(uid=uid)
            if any(g.get('group_id') == gid for g in groups):
                h._send(json.dumps({'error': f'group_id already exists: {gid}'}), status=409); return True
            groups.append(grp)
            _sj._set_nested(cfg, path_keys, groups)
            _sj.write_config(cfg, uid)
            h._send(json.dumps({'ok': True, 'group_id': gid}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/group-update':
        try:
            data = h._read_json_body()
            grp  = data.get('group')
            if not grp or not grp.get('group_id'):
                h._send(json.dumps({'error': 'group_id required'}), status=400); return True
            gid = grp['group_id'].strip()
            cfg, groups, path_keys = _sj.get_keyword_groups(uid=uid)
            idx = next((i for i, g in enumerate(groups) if g.get('group_id') == gid), None)
            if idx is None:
                h._send(json.dumps({'error': f'group_id not found: {gid}'}), status=404); return True
            groups[idx] = {**groups[idx], **grp}
            _sj._set_nested(cfg, path_keys, groups)
            _sj.write_config(cfg, uid)
            h._send(json.dumps({'ok': True, 'group_id': gid}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    elif path == '/api/preferences':
        try:
            data = h._read_json_body()
            cfg  = _sj.read_config(uid)
            pref = cfg.setdefault('preferences', {})
            js   = cfg.setdefault('job_search', {})
            st   = cfg.setdefault('stepstone', {})
            for k in ('preferred_locations', 'preferred_work_mode',
                      'salary_expectation_eur_monthly', 'preferred_domains',
                      'preferred_level', 'language_skills'):
                if k in data:
                    pref[k] = data[k]
            if 'stepstone_enabled'    in data: st['enabled']               = data['stepstone_enabled']
            if 'auto_default_answers' in data: cfg['auto_default_answers'] = data['auto_default_answers']
            if 'date_range_days'      in data: js['date_range_days']       = data['date_range_days']
            if 'max_display'          in data: js['max_display']           = data['max_display']
            _sj.write_config(cfg, uid)
            h._send(json.dumps({'ok': True}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    return False
