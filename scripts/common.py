#!/usr/bin/env python3
"""
scripts/common.py — shared constants and utilities used across LinkedIn CV scripts.
"""

import json
import os
import queue
import shutil
import subprocess
import threading
import time

# Path to the uvx executable.
# Resolution order:
#   1. UVX_PATH env var (set this in CI or when uvx is not on PATH)
#   2. shutil.which("uvx") — PATH search
#   3. Known Windows pip user-install paths (pip install uv lands here)
#   4. Bare "uvx" — let subprocess find it at call time
def _find_uvx() -> str:
    if v := os.environ.get("UVX_PATH"):
        return v
    if v := shutil.which("uvx"):
        return v
    import glob
    patterns = [
        os.path.expandvars(r"%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.*\LocalCache\local-packages\Python*\Scripts\uvx.exe"),
        os.path.expandvars(r"%APPDATA%\Python\Python*\Scripts\uvx.exe"),
        os.path.expanduser(r"~\.local\bin\uvx"),
        os.path.expanduser(r"~\.cargo\bin\uvx"),
    ]
    for pat in patterns:
        matches = glob.glob(pat)
        if matches:
            return matches[0]
    return "uvx"

UVX: str = _find_uvx()


# ─────────────────────────────────────────────
# Non-blocking MCP process helpers
# ─────────────────────────────────────────────

def _stdout_reader_loop(stdout, q: queue.Queue) -> None:
    """Background thread: drain stdout into queue; put None sentinel on EOF."""
    try:
        for line in stdout:
            q.put(line)
    except Exception:
        pass
    q.put(None)


def make_mcp_proc() -> subprocess.Popen:
    """
    Spawn linkedin-scraper-mcp with a background reader thread.

    Fixes two bugs in the naive Popen approach:
    - P0-2 stderr deadlock: stderr → DEVNULL (not PIPE) so MCP never blocks
      waiting for stderr to be consumed.
    - P0-1 readline() hang: stdout lines are drained by a daemon thread into a
      Queue, so send_recv() can honour its timeout even when MCP is silent.
    """
    proc = subprocess.Popen(
        [UVX, "linkedin-scraper-mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,   # prevents stderr pipe deadlock
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    proc._line_queue: queue.Queue = queue.Queue()
    proc._reader = threading.Thread(
        target=_stdout_reader_loop,
        args=(proc.stdout, proc._line_queue),
        daemon=True,
    )
    proc._reader.start()
    return proc


def send_recv(proc: subprocess.Popen, msg: dict, timeout: float = 60) -> dict | None:
    """
    Send a JSON-RPC message and return the matching response within *timeout* seconds.

    Requires proc created by make_mcp_proc() for true non-blocking reads.
    Falls back to legacy blocking readline() for procs created without the queue.
    """
    msg_id = msg.get("id")
    try:
        proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        proc.stdin.flush()
    except (BrokenPipeError, OSError):
        return None

    q = getattr(proc, "_line_queue", None)
    deadline = time.monotonic() + timeout

    if q is not None:
        # Non-blocking path: drain the queue attached by make_mcp_proc()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                line = q.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue
            if line is None:        # EOF sentinel — process exited
                return None
            try:
                resp = json.loads(line.strip())
                if resp.get("id") == msg_id:
                    return resp
                # Ignore JSON-RPC notifications (no "id" or different id)
            except (json.JSONDecodeError, ValueError):
                continue
    else:
        # Fallback: legacy blocking readline (proc not from make_mcp_proc)
        while time.monotonic() < deadline:
            raw = proc.stdout.readline()
            if not raw:
                time.sleep(0.05)
                continue
            try:
                resp = json.loads(raw.strip())
                if resp.get("id") == msg_id:
                    return resp
            except (json.JSONDecodeError, ValueError):
                continue
        return None
