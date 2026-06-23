#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_jd_analysis.py — Two-phase JD analysis via claude CLI (no API key required).

Phase E1: Sonnet, no tools, outputs JSON in stdout  → Python writes jd_analysis.json
Phase E2: Sonnet, Read+Write+WebSearch, no cv_parsed → updates existing jd_analysis.json
          Triggered only when match_score >= threshold AND decision_score >= threshold.

Usage (called by Orchestrator via Bash tool):
  python3 scripts/run_jd_analysis.py \\
      --uid leon \\
      --group_id group-pdm \\
      --job_folder group-pdm_Trivago_Data-Analyst_20260619 \\
      [--source linkedin|linkedin_posting|stepstone]

Prerequisite: Orchestrator must write jd_text.txt into the job folder before calling.
"""
import argparse
import atexit
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

PROJECT_DIR = Path(__file__).resolve().parent.parent
AGENTS_DIR  = PROJECT_DIR / '.claude' / 'agents'
CONFIG_PATH = PROJECT_DIR / 'config' / 'model_config.json'


# ── Config ────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _get_model(cfg: dict, key: str, default: str) -> str:
    return cfg.get('agents', {}).get(key, default)


def _get_threshold(cfg: dict, key: str, default: int) -> int:
    return int(cfg.get('thresholds', {}).get(key, default))


def _load_agent_prompt(name: str) -> str:
    """Read agent .md file stripping YAML frontmatter."""
    content = (AGENTS_DIR / f'{name}.md').read_text(encoding='utf-8')
    if content.startswith('---'):
        end = content.index('---', 3)
        content = content[end + 3:].lstrip('\n')
    return content



# ── JSON extraction ───────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Extract JSON from Phase E1 stdout (handles ```json``` wrapper or bare {})."""
    m = re.search(r'```json\s*([\s\S]+?)\s*```', text)
    if m:
        return json.loads(m.group(1))
    m = re.search(r'\{[\s\S]+\}', text)
    if m:
        return json.loads(m.group(0))
    raise ValueError('No valid JSON found in Phase E1 output')


# ── Phase E1: Sonnet, no tools, JSON in stdout ────────────────────────────────

def _run_phase1(prompt: str, model: str, _claude: str) -> dict:
    for attempt in range(4):
        r = subprocess.run(
            [_claude, '--dangerously-skip-permissions', '-p', '-', '--model', model],
            input=prompt,
            capture_output=True, text=True, encoding='utf-8',
            timeout=480, cwd=str(PROJECT_DIR),
        )
        if r.returncode == 0:
            return _extract_json(r.stdout)
        stderr_lower = (r.stderr or '').lower()
        if any(s in stderr_lower for s in ('rate', '429', 'limit', 'overloaded')):
            wait = 30 * (2 ** attempt) + random.uniform(0, 20)
            print(f'[phase1 rate limit] waiting {wait:.0f}s before retry {attempt+1}/4...',
                  file=sys.stderr, flush=True)
            time.sleep(wait)
        else:
            raise RuntimeError(f'Phase E1 claude exited {r.returncode}: {(r.stderr or "")[:500]}')
    raise RuntimeError('Phase E1 failed after 4 retries')


# ── Phase E2: Sonnet, Read+Write+WebSearch, no cv_parsed ─────────────────────

def _run_phase2(system_phase2: str, job_dir: Path, jd_data: dict,
                jd_text: str, model: str, _claude: str) -> None:
    phase2_context = (
        f'job_dir: {job_dir}\n'
        f'company: {jd_data.get("company", "")}\n'
        f'title: {jd_data.get("title", "")}\n'
        f'match_score: {jd_data.get("match_score", 0)}\n'
        f'decision_score: {jd_data.get("decision_score", 0)}\n\n'
        f'JD text (first 3000 chars for WebSearch context):\n{jd_text[:3000]}'
    )
    prompt = f'{system_phase2}\n\n---\n\n{phase2_context}'

    for attempt in range(4):
        r = subprocess.run(
            [_claude, '--dangerously-skip-permissions', '-p', '-',
             '--allowedTools', 'Read,Write,WebSearch',
             '--model', model],
            input=prompt,
            capture_output=True, text=True, encoding='utf-8',
            timeout=300, cwd=str(PROJECT_DIR),
        )
        if r.returncode == 0:
            return
        stderr_lower = (r.stderr or '').lower()
        if any(s in stderr_lower for s in ('rate', '429', 'limit', 'overloaded')):
            wait = 30 * (2 ** attempt) + random.uniform(0, 20)
            print(f'[phase2 rate limit] waiting {wait:.0f}s before retry {attempt+1}/4...',
                  file=sys.stderr, flush=True)
            time.sleep(wait)
        else:
            print(f'WARN: Phase E2 failed (non-fatal), exit={r.returncode}: '
                  f'{(r.stderr or "")[:300]}', file=sys.stderr)
            return
    print('WARN: Phase E2 persisted after 4 retries (non-fatal)', file=sys.stderr)


# ── Legacy fallback: original single-pass full pipeline ──────────────────────

def _run_legacy(prompt_legacy: str, model_legacy: str, _claude: str,
                job_dir: Path, source: str, group_id: str) -> int:
    """Fallback to original full-pipeline claude CLI call (with WebSearch tools)."""
    jd_out = job_dir / 'jd_analysis.json'
    for attempt in range(4):
        r = subprocess.run(
            [_claude, '--dangerously-skip-permissions', '-p', '-',
             '--allowedTools', 'Read,Write,WebSearch',
             '--model', model_legacy],
            input=prompt_legacy,
            capture_output=True, text=True, encoding='utf-8',
            timeout=600, cwd=str(PROJECT_DIR),
        )
        if r.returncode == 0:
            break
        stderr_lower = (r.stderr or '').lower()
        if any(s in stderr_lower for s in ('rate', '429', 'limit', 'overloaded')):
            wait = 30 * (2 ** attempt) + random.uniform(0, 20)
            print(f'[legacy rate limit] waiting {wait:.0f}s before retry {attempt+1}/4...',
                  file=sys.stderr, flush=True)
            time.sleep(wait)
        else:
            print(f'ERROR: legacy claude exited {r.returncode}', file=sys.stderr)
            if r.stderr:
                print(r.stderr[:2000], file=sys.stderr)
            return 1
    else:
        print('ERROR: legacy persisted after 4 retries', file=sys.stderr)
        return 1

    if not jd_out.exists():
        print('ERROR: jd_analysis.json was not written by legacy agent', file=sys.stderr)
        return 1
    try:
        data = json.loads(jd_out.read_text(encoding='utf-8'))
        data['_source']   = source
        data['_group_id'] = group_id
        jd_out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        print(f'WARN: could not inject _source/_group_id in legacy: {e}', file=sys.stderr)
    return 0


# ── JD concurrency slot (R4 code-enforced parallel limit) ────────────────────

_JD_MAX_PARALLEL = 3
_JD_LOCK_DIR = Path.home() / '.linkedin-mcp' / 'jd_locks'


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # process exists, no permission to signal — treat as alive
    except OSError:
        return False


def _acquire_jd_slot(timeout: int = 600) -> int | None:
    """Acquire one of _JD_MAX_PARALLEL slots. Returns slot index, or None on timeout."""
    _JD_LOCK_DIR.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    logged_wait = False
    while time.monotonic() < deadline:
        for slot in range(_JD_MAX_PARALLEL):
            lock_path = _JD_LOCK_DIR / f'slot_{slot}.lock'
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return slot
            except FileExistsError:
                try:
                    pid = int(lock_path.read_text().strip())
                    if not _is_pid_alive(pid):
                        lock_path.unlink(missing_ok=True)
                except Exception:
                    pass
        if not logged_wait:
            print(f'[jd-slot] all {_JD_MAX_PARALLEL} slots busy, waiting…',
                  file=sys.stderr, flush=True)
            logged_wait = True
        time.sleep(5)
    return None


def _release_jd_slot(slot: int) -> None:
    try:
        (_JD_LOCK_DIR / f'slot_{slot}.lock').unlink(missing_ok=True)
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--uid',        required=True)
    ap.add_argument('--group_id',   required=True)
    ap.add_argument('--job_folder', required=True)
    ap.add_argument('--source',     default='linkedin')
    args = ap.parse_args()

    uid        = args.uid
    group_id   = args.group_id
    job_folder = args.job_folder
    source     = args.source

    slot = _acquire_jd_slot()
    if slot is None:
        print('ERROR: could not acquire JD analysis slot (timeout 10 min)', file=sys.stderr)
        return 1
    atexit.register(_release_jd_slot, slot)

    _start_delay = random.uniform(0, 5)
    if _start_delay > 0.5:
        print(f'[jitter] startup delay {_start_delay:.1f}s', file=sys.stderr, flush=True)
        time.sleep(_start_delay)

    output_dir = PROJECT_DIR / 'users' / uid / 'output'
    job_dir    = output_dir / job_folder
    jd_out     = job_dir / 'jd_analysis.json'

    # ── Read JD text ──────────────────────────────────────────────────────────
    jd_file = job_dir / 'jd_text.txt'
    if not jd_file.exists():
        print(f'ERROR: jd_text.txt not found: {jd_file}', file=sys.stderr)
        return 1

    raw_jd = jd_file.read_text(encoding='utf-8')
    if raw_jd.startswith('_') and '\n---\n' in raw_jd:
        header, _, jd_text = raw_jd.partition('\n---\n')
        for line in header.splitlines():
            if line.startswith('_source:'):
                source = line.split(':', 1)[1].strip()
    else:
        jd_text = raw_jd

    # ── Read cv_parsed ────────────────────────────────────────────────────────
    cv_file = output_dir / f'cv_parsed_{group_id}.json'
    if not cv_file.exists():
        cands = sorted(output_dir.glob('cv_parsed_*.json'))
        if not cands:
            print(f'ERROR: No cv_parsed found for group {group_id}', file=sys.stderr)
            return 1
        cv_file = cands[0]
        print(f'WARN: cv_parsed_{group_id}.json not found, using {cv_file.name}',
              file=sys.stderr)
    cv_json = cv_file.read_text(encoding='utf-8')

    # ── Read user config ──────────────────────────────────────────────────────
    cfg_file = PROJECT_DIR / 'users' / uid / 'config.json'
    preferences: dict = {}
    keyword_groups: list = []
    if cfg_file.exists():
        try:
            cfg_data       = json.loads(cfg_file.read_text(encoding='utf-8'))
            preferences    = cfg_data.get('preferences', {})
            keyword_groups = cfg_data.get('job_search', {}).get('keyword_groups', [])
        except Exception:
            pass

    # ── Load model config ─────────────────────────────────────────────────────
    app_cfg      = _load_config()
    model_phase1 = _get_model(app_cfg, 'jd-analyzer-phase1', 'claude-sonnet-4-6')
    model_phase2 = _get_model(app_cfg, 'jd-analyzer-phase2', 'claude-sonnet-4-6')
    model_legacy = _get_model(app_cfg, 'jd-analyzer',        'claude-sonnet-4-6')
    thr_match    = _get_threshold(app_cfg, 'jd_phase2_min_match_score',    65)
    thr_decision = _get_threshold(app_cfg, 'jd_phase2_min_decision_score', 60)

    _claude = shutil.which('claude') or 'claude'

    # ── Build shared context (for Phase E1 prompt) ────────────────────────────
    kg_summary = json.dumps(
        [{'group_id': g.get('group_id'), 'group_label': g.get('group_label'),
          'job_family': g.get('job_family', [])}
         for g in keyword_groups],
        ensure_ascii=False,
    )
    cv_context = (
        f'cv_parsed for group {group_id} (use this as the candidate CV — '
        f'do NOT read cv_parsed from file, it is provided here):\n'
        f'{cv_json}\n\n'
        f'preferences:\n{json.dumps(preferences, ensure_ascii=False, indent=2)}\n\n'
        f'keyword_groups summary (for job_family_fit calculation):\n{kg_summary}'
    )

    job_context = (
        f'uid: {uid}\n'
        f'group_id: {group_id}\n'
        f'job_folder: {job_folder}\n\n'
        f'JD text:\n{jd_text}'
    )

    # ── Phase E1 ──────────────────────────────────────────────────────────────
    try:
        system_phase1 = _load_agent_prompt('jd-analyzer-phase1')
    except FileNotFoundError:
        print('WARN: jd-analyzer-phase1.md not found, using legacy pipeline', file=sys.stderr)
        system_phase1 = None

    if system_phase1:
        phase1_prompt = f'{system_phase1}\n\n---\n\n{cv_context}\n\n{job_context}'
        try:
            jd_data = _run_phase1(phase1_prompt, model_phase1, _claude)
        except Exception as e:
            print(f'WARN: Phase E1 failed ({e}), falling back to legacy pipeline',
                  file=sys.stderr)
            system_phase1 = None

    if not system_phase1:
        # Legacy fallback: original single-pass full pipeline
        system_legacy = _load_agent_prompt('jd-analyzer')
        legacy_prompt = (
            f'{system_legacy}\n\n---\n\n{cv_context}\n\n'
            f'uid: {uid}\ngroup_id: {group_id}\n'
            f'job_folder (absolute path): {job_dir}\n'
            f'output_dir (absolute path): {output_dir}\n'
            f'Write jd_analysis.json to: {jd_out}\n\n'
            f'JD text:\n{jd_text}'
        )
        return _run_legacy(legacy_prompt, model_legacy, _claude, job_dir, source, group_id)

    # Inject _source and _group_id, write jd_analysis.json
    jd_data['_source']   = source
    jd_data['_group_id'] = group_id
    jd_out.write_text(json.dumps(jd_data, ensure_ascii=False, indent=2), encoding='utf-8')

    match_score    = jd_data.get('match_score', 0)
    decision_score = jd_data.get('decision_score', 0)

    # ── Phase E2 (conditional) ────────────────────────────────────────────────
    if match_score >= thr_match and decision_score >= thr_decision:
        try:
            system_phase2 = _load_agent_prompt('jd-analyzer-phase2')
            _run_phase2(system_phase2, job_dir, jd_data, jd_text, model_phase2, _claude)
        except FileNotFoundError:
            print('WARN: jd-analyzer-phase2.md not found, skipping Phase E2', file=sys.stderr)
        except Exception as e:
            print(f'WARN: Phase E2 error (non-fatal): {e}', file=sys.stderr)
    else:
        print(
            f'[phase2 skip] match={match_score} decision={decision_score} '
            f'(thresholds: match≥{thr_match} decision≥{thr_decision})',
            file=sys.stderr,
        )

    # Reload final result (Phase E2 may have updated jd_analysis.json)
    try:
        final = json.loads(jd_out.read_text(encoding='utf-8'))
    except Exception:
        final = jd_data

    score   = final.get('match_score', '?')
    company = final.get('company', '?')
    title   = final.get('title', '?')
    size    = (final.get('company_info') or {}).get('size', 'unavailable')
    print(f'JD_ANALYZED_OK: {company}_{title} score={score} company_size={size}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
