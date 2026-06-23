#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server_ai.py — AI endpoint helpers and HTTP route handlers extracted from server.py
(Week 4 split).

Contains:
  _extract_qa / _build_form_fields / _ATS_FIELD_MAP  — data helpers
  handle_get   — GET  /api/form-fields
  handle_post  — POST /api/form-assist, /api/optimize-exp,
                      /api/default-answers, /api/finetune-answer  (all SSE)
"""
import json
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from server_jobs import (  # noqa: E402
    get_output_dir, _user_dir,
    _jobs_cache, _jobs_cache_lock,
)

ANSI_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

_MODEL_CFG: dict | None = None

def _get_server_model(key: str) -> str:
    """Read model ID from config/model_config.json (lazy-loaded, cached)."""
    global _MODEL_CFG
    if _MODEL_CFG is None:
        try:
            cfg_path = Path(__file__).resolve().parent.parent / 'config' / 'model_config.json'
            _MODEL_CFG = json.loads(cfg_path.read_text(encoding='utf-8'))
        except Exception:
            _MODEL_CFG = {}
    return _MODEL_CFG.get('server_endpoints', {}).get(key, 'claude-haiku-4-5')

_SKIP_PREFIXES = (
    'Warning:', 'The `', "To use it,", "Which would",
    "1. **", "2. **", "Available", "Please tell",
)

# ── AI concurrency guard ──────────────────────────────────────────────────────
# Limits simultaneous claude-p subprocesses to prevent Claude API TPM spikes.
_AI_ACTIVE = 0
_AI_MAX    = 3
_AI_LOCK   = threading.Lock()

def _ai_acquire() -> bool:
    global _AI_ACTIVE
    with _AI_LOCK:
        if _AI_ACTIVE >= _AI_MAX:
            return False
        _AI_ACTIVE += 1
        return True

def _ai_release():
    global _AI_ACTIVE
    with _AI_LOCK:
        _AI_ACTIVE = max(0, _AI_ACTIVE - 1)


# ── Q&A parser ────────────────────────────────────────────────────────────────
def _extract_qa(text: str) -> list:
    """Parse Q&A from either JSON or markdown output produced by claude CLI."""
    try:
        clean = re.sub(r'```(?:json)?\s*|\s*```', '', text)
        m = re.search(r'\{"default_answers"\s*:\s*\[[\s\S]*?\]\s*\}', clean)
        if m:
            parsed = json.loads(m.group())
            if parsed.get('default_answers'):
                return parsed['default_answers']
    except Exception:
        pass
    pairs = []
    parts = re.split(r'(?m)^##\s+Q\d+\s*', text)
    for part in parts[1:]:
        lines = part.strip().split('\n')
        q = re.sub(r'^[^\w]*', '', lines[0]).strip()
        rest = '\n'.join(lines[1:])
        a_match = re.search(r'\*\*A(?:nswer)?:\*\*\s*([\s\S]+)', rest)
        if not a_match:
            continue
        a_raw = a_match.group(1).strip()
        a_raw = re.sub(r'\*\*(.*?)\*\*', r'\1', a_raw)
        a_raw = re.sub(r'\*(.*?)\*', r'\1', a_raw)
        a_raw = re.sub(r'^[-—]+$', '', a_raw, flags=re.MULTILINE)
        a_clean = re.sub(r'\s+', ' ', a_raw).strip()
        if q and a_clean:
            pairs.append({'question': q, 'answer': a_clean})
    return pairs[:5]


# ── ATS field map ─────────────────────────────────────────────────────────────
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
_ATS_FIELD_MAP["generic"] = _ATS_FIELD_MAP["workday"]


def _parse_duration(duration: str) -> dict:
    """Parse "2024", "2024 – 2025", "09/2024 – 12/2025" → {start_year, start_month, ...}."""
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
    """Map cv_parsed to ATS form field cards, optionally reordering bullets by JD relevance."""
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
                'country':     exp.get('country', 'Germany'),
                'city':        exp.get('city', ''),
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
            dur = _parse_duration(edu.get('duration', edu.get('years', edu.get('year', ''))))
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
        'ats_type':        ats_type,
        'work_experience': _exp_cards(cv_parsed.get('experience', [])),
        'education':       _edu_cards(cv_parsed.get('education', [])),
    }


# ── SSE helper ────────────────────────────────────────────────────────────────
def _sse_headers(h) -> None:
    h.send_response(200)
    h.send_header('Content-Type', 'text/event-stream')
    h.send_header('Cache-Control', 'no-cache')
    h.send_header('Access-Control-Allow-Origin', '*')
    h.end_headers()


def _sse_stream(h, proc) -> None:
    """Stream proc stdout as SSE text chunks; send done event."""
    try:
        for line in proc.stdout:
            stripped = ANSI_RE.sub('', line.rstrip())
            if stripped:
                chunk = json.dumps({'text': stripped}, ensure_ascii=False)
                h.wfile.write(f'data: {chunk}\n\n'.encode('utf-8'))
                h.wfile.flush()
        proc.wait()
        h.wfile.write(b'data: {"done":true}\n\n')
        h.wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
        pass


# ── Route handlers ────────────────────────────────────────────────────────────
def handle_get(path: str, qs: dict, uid: str, h) -> bool:
    """Handle GET; return True if handled."""

    if path == '/api/form-fields':
        try:
            inner_qs   = parse_qs(urlparse(h.path).query)
            job_folder = inner_qs.get('job_folder', [''])[0].strip()
            ats_type   = inner_qs.get('ats_type', ['workday'])[0].strip()
            if not job_folder:
                h._send(json.dumps({'error': 'job_folder required'}), status=400); return True
            output_dir = get_output_dir(uid)
            job_path   = (output_dir / job_folder).resolve()
            try:
                job_path.relative_to(output_dir.resolve())
            except ValueError:
                h._send(json.dumps({'error': 'invalid path'}), status=400); return True
            jd_file = job_path / 'jd_analysis.json'
            if not jd_file.exists():
                h._send(json.dumps({'error': 'jd_analysis.json not found'}), status=404); return True
            group_id_param = inner_qs.get('group_id', [''])[0].strip()
            group_id = group_id_param if (group_id_param and group_id_param != '—') else job_folder.split('_')[0]
            cv_file = output_dir / f'cv_parsed_{group_id}.json'
            if not cv_file.exists():
                candidates = sorted(output_dir.glob('cv_parsed_*.json'))
                cv_file = candidates[0] if candidates else None
                if not cv_file:
                    h._send(json.dumps({'error': f'cv_parsed not found: {group_id}'}), status=404); return True
            cv_parsed = json.loads(cv_file.read_text(encoding='utf-8'))
            jd_data   = json.loads(jd_file.read_text(encoding='utf-8'))
            result = _build_form_fields(cv_parsed, ats_type, jd_data)
            result['recommended_emphasis'] = jd_data.get('recommended_emphasis', [])
            result['matched_skills']       = jd_data.get('matched_skills', [])
            result['exp_optimized']        = jd_data.get('exp_optimized', {})
            h._send(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    if path == '/api/cl-status':
        try:
            inner_qs   = parse_qs(urlparse(h.path).query)
            job_folder = inner_qs.get('job_folder', [''])[0].strip()
            if not job_folder:
                h._send(json.dumps({'has_cl': False})); return True
            output_dir = get_output_dir(uid)
            job_path   = (output_dir / job_folder).resolve()
            try:
                job_path.relative_to(output_dir.resolve())
            except ValueError:
                h._send(json.dumps({'has_cl': False})); return True
            has_cl = any((job_path / f).exists() for f in ('cover_letter.pdf', 'cover_letter.docx'))
            h._send(json.dumps({'has_cl': has_cl, 'folder': str(job_path) if has_cl else ''},
                               ensure_ascii=False))
        except Exception as e:
            h._send(json.dumps({'has_cl': False, 'error': str(e)}))
        return True

    return False


def handle_post(path: str, qs: dict, uid: str, h) -> bool:
    """Handle POST; return True if handled."""
    claude_bin = shutil.which('claude') or 'claude'

    if path == '/api/form-assist':
        try:
            data        = h._read_json_body()
            job_folder  = (data.get('job_folder') or '').strip()
            form_fields = [f for f in (data.get('form_fields') or []) if str(f).strip()]
            if not job_folder:
                h._send(json.dumps({'error': 'job_folder required'}), status=400); return True
            output_dir = get_output_dir(uid)
            job_path   = (output_dir / job_folder).resolve()
            try:
                job_path.relative_to(output_dir.resolve())
            except ValueError:
                h._send(json.dumps({'error': 'invalid job_folder path'}), status=400); return True
            if not job_path.is_dir():
                h._send(json.dumps({'error': f'not found: {job_folder}'}), status=404); return True
            fields_text = '\n'.join(f'- {f}' for f in form_fields)
            prompt = (
                f'表单助手\n'
                f'job_folder: "{job_folder}"\n'
                f'form_fields:\n{fields_text}'
            )
            if not _ai_acquire():
                h._send(json.dumps({'error': 'AI 服务繁忙，请稍后重试', 'retry_after': 10}), status=429)
                return True
            try:
                _sse_headers(h)
                proc = subprocess.Popen(
                    [claude_bin, '-p', prompt,
                     '--model', _get_server_model('form_assist')],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(_user_dir(uid)), text=True,
                    encoding='utf-8', errors='replace',
                )
                _sse_stream(h, proc)
            finally:
                _ai_release()
        except Exception as e:
            try:
                h.wfile.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode('utf-8'))
                h.wfile.flush()
            except Exception:
                pass
        return True

    elif path == '/api/optimize-exp':
        try:
            import tempfile as _tmp
            data        = h._read_json_body()
            job_folder  = (data.get('job_folder') or '').strip()
            exp_header  = (data.get('exp_header') or '').strip()
            desc_full   = (data.get('desc_full') or '').strip()
            if not job_folder:
                h._send(json.dumps({'error': 'job_folder required'}), status=400); return True
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
            if not _ai_acquire():
                h._send(json.dumps({'error': 'AI 服务繁忙，请稍后重试', 'retry_after': 10}), status=429)
                return True
            try:
                _sse_headers(h)
                proc = subprocess.Popen(
                    [claude_bin, '-p', prompt,
                     '--model', _get_server_model('optimize_exp'),
                     '--disallowedTools', 'Read,Glob,Grep,Write,Edit,WebFetch,WebSearch,TodoWrite,TodoRead'],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    cwd=_tmp.gettempdir(), text=True,
                    encoding='utf-8', errors='replace',
                )
                try:
                    full_lines = []
                    for line in proc.stdout:
                        stripped = ANSI_RE.sub('', line.rstrip())
                        if stripped and not any(stripped.startswith(p) for p in _SKIP_PREFIXES):
                            full_lines.append(stripped)
                            chunk = json.dumps({'text': stripped + '\n'}, ensure_ascii=False)
                            h.wfile.write(f'data: {chunk}\n\n'.encode('utf-8'))
                            h.wfile.flush()
                    proc.wait()
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
                    h.wfile.write(b'data: {"done":true}\n\n')
                    h.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            finally:
                _ai_release()
        except Exception as e:
            try:
                h.wfile.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode('utf-8'))
                h.wfile.flush()
            except Exception:
                pass
        return True

    elif path == '/api/default-answers':
        try:
            data       = h._read_json_body()
            job_folder = (data.get('job_folder') or '').strip()
            if not job_folder:
                h._send(json.dumps({'error': 'job_folder required'}), status=400); return True
            jd_file = get_output_dir(uid) / job_folder / 'jd_analysis.json'
            if jd_file.exists():
                jd = json.loads(jd_file.read_text(encoding='utf-8'))
                cached = jd.get('default_answers')
                if cached:
                    h._send(json.dumps({'cached': True, 'default_answers': cached}, ensure_ascii=False))
                    return True
            else:
                jd = {}
            if not shutil.which('claude'):
                h._send(json.dumps({'error': 'claude CLI not found in PATH'}), status=503); return True
            company   = jd.get('company', '')
            title     = jd.get('title', '')
            cores     = jd.get('core_responsibilities', [])[:5]
            matched   = jd.get('matched_skills', [])[:8]
            cores_str = '\n'.join(
                f'- {r.get("responsibility", r) if isinstance(r, dict) else r}'
                for r in cores)
            matched_str = ', '.join(
                (m if isinstance(m, str) else m.get('skill', '')) for m in matched)
            prompt = (
                f'Generate exactly 5 common interview Q&A for the role: {title} at {company}.\n'
                f'Core responsibilities:\n{cores_str}\n'
                f'Candidate matched skills: {matched_str}\n'
                'Write answers in first person, 3-5 sentences each. English only.\n'
                'Output ONLY valid JSON, no markdown, no code fences, no extra text:\n'
                '{"default_answers":[{"question":"...","answer":"..."}]}'
            )
            if not _ai_acquire():
                h._send(json.dumps({'error': 'AI 服务繁忙，请稍后重试', 'retry_after': 10}), status=429)
                return True
            try:
                _sse_headers(h)
                proc = subprocess.Popen(
                    [claude_bin, '-p', prompt,
                     '--model', _get_server_model('default_answers_inline')],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(_user_dir(uid)), text=True,
                    encoding='utf-8', errors='replace',
                )
                try:
                    buf_server = ''
                    for line in proc.stdout:
                        stripped = ANSI_RE.sub('', line.rstrip())
                        if stripped:
                            buf_server += stripped + ' '
                            chunk = json.dumps({'text': stripped}, ensure_ascii=False)
                            h.wfile.write(f'data: {chunk}\n\n'.encode('utf-8'))
                            h.wfile.flush()
                    proc.wait()
                    h.wfile.write(b'data: {"done":true}\n\n')
                    h.wfile.flush()
                    try:
                        answers = _extract_qa(buf_server)
                        if answers and jd_file.exists():
                            detail = json.loads(jd_file.read_text(encoding='utf-8'))
                            detail['default_answers'] = answers
                            jd_file.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding='utf-8')
                            with _jobs_cache_lock:
                                _jobs_cache.pop(uid, None)
                    except Exception:
                        pass
                except (BrokenPipeError, ConnectionResetError):
                    pass
            finally:
                _ai_release()
        except Exception as e:
            try:
                h.wfile.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode('utf-8'))
                h.wfile.flush()
            except Exception:
                pass
        return True

    elif path == '/api/finetune-answer':
        try:
            data        = h._read_json_body()
            job_folder  = (data.get('job_folder') or '').strip()
            question    = (data.get('question') or '').strip()
            cur_answer  = (data.get('current_answer') or '').strip()
            direction   = (data.get('direction') or '').strip()
            if not job_folder:
                h._send(json.dumps({'error': 'job_folder required'}), status=400); return True
            prompt = (
                f'default-answers\n'
                f'job_folder: "{job_folder}"\n'
                f'finetune: true\n'
                f'question: {question}\n'
                f'current_answer: {cur_answer}\n'
                f'direction: {direction}'
            )
            if not _ai_acquire():
                h._send(json.dumps({'error': 'AI 服务繁忙，请稍后重试', 'retry_after': 10}), status=429)
                return True
            try:
                _sse_headers(h)
                proc = subprocess.Popen(
                    [claude_bin, '-p', prompt,
                     '--model', _get_server_model('finetune_answer')],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(_user_dir(uid)), text=True,
                    encoding='utf-8', errors='replace',
                )
                _sse_stream(h, proc)
            finally:
                _ai_release()
        except Exception as e:
            try:
                h.wfile.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode('utf-8'))
                h.wfile.flush()
            except Exception:
                pass
        return True

    elif path == '/api/generate-cl':
        def _stream_proc(proc):
            """Stream proc stdout as SSE lines; return returncode."""
            for line in proc.stdout:
                stripped = ANSI_RE.sub('', line.rstrip())
                if stripped:
                    h.wfile.write(
                        f'data: {json.dumps({"text": stripped}, ensure_ascii=False)}\n\n'.encode('utf-8'))
                    h.wfile.flush()
            proc.wait()
            return proc.returncode

        try:
            data       = h._read_json_body()
            job_folder = (data.get('job_folder') or '').strip()
            if not job_folder:
                h._send(json.dumps({'error': 'job_folder required'}), status=400); return True
            output_dir  = get_output_dir(uid)
            job_path    = (output_dir / job_folder).resolve()
            try:
                job_path.relative_to(output_dir.resolve())
            except ValueError:
                h._send(json.dumps({'error': 'invalid path'}), status=400); return True
            project_dir = Path(__file__).resolve().parent.parent
            md_path     = job_path / 'cover_letter_draft.md'
            _sse_headers(h)
            try:
                # Step 1: generate draft if needed
                if not md_path.exists():
                    draft_script = project_dir / 'scripts' / 'gen_cl_draft.py'
                    proc = subprocess.Popen(
                        [sys.executable, str(draft_script),
                         '--job_folder', job_folder, '--uid', uid],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        cwd=str(project_dir), text=True,
                        encoding='utf-8', errors='replace',
                    )
                    rc = _stream_proc(proc)
                    if rc != 0:
                        h.wfile.write(
                            f'data: {json.dumps({"error": f"Draft generation failed (exit {rc})"})}\n\n'.encode())
                        h.wfile.flush()
                        return True

                # Step 2: convert md → pdf + docx
                gen_script = project_dir / 'scripts' / 'gen_cover_letter.py'
                proc = subprocess.Popen(
                    [sys.executable, str(gen_script),
                     '--job_folder', job_folder, '--uid', uid, '--format', 'all'],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    cwd=str(project_dir), text=True,
                    encoding='utf-8', errors='replace',
                )
                rc = _stream_proc(proc)
                if rc != 0:
                    h.wfile.write(
                        f'data: {json.dumps({"error": f"Conversion failed (exit {rc})"})}\n\n'.encode())
                else:
                    h.wfile.write(
                        f'data: {json.dumps({"done": True, "folder": str(job_path)}, ensure_ascii=False)}\n\n'.encode())
                h.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
        except Exception as e:
            try:
                h.wfile.write(f'data: {json.dumps({"error": str(e)})}\n\n'.encode('utf-8'))
                h.wfile.flush()
            except Exception:
                pass
        return True

    elif path == '/api/open-folder':
        try:
            data   = h._read_json_body()
            folder = (data.get('path') or '').strip()
            if not folder:
                h._send(json.dumps({'error': 'path required'}), status=400); return True
            project_dir = Path(__file__).resolve().parent.parent
            try:
                Path(folder).resolve().relative_to(project_dir.resolve())
            except ValueError:
                h._send(json.dumps({'error': 'invalid path'}), status=403); return True
            resolved = str(Path(folder).resolve())
            subprocess.Popen(f'explorer "{resolved}"', shell=True)
            h._send(json.dumps({'ok': True}))
        except Exception as e:
            h._send(json.dumps({'error': str(e)}), status=500)
        return True

    return False
