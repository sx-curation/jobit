#!/usr/bin/env python3
"""
scripts/linkedin_search.py

Calls linkedin-scraper-mcp via JSON-RPC to search for jobs.
Handles the full MCP protocol handshake and tool invocation.

Usage:
  python3 scripts/linkedin_search.py \
      --keywords "Marketing Analytics Specialist" \
      --location "Germany" \
      --date-posted past_month \
      --max-pages 1
"""

import json
import sys
import argparse

from common import UVX, make_mcp_proc, send_recv

# Fix Windows GBK crash: reconfigure stdout/stderr to UTF-8 immediately at import time
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def search_jobs(keywords: str, location: str, date_posted: str = "past_month",
                max_pages: int = 1, timeout: int = 60) -> dict:
    """
    Launch linkedin-scraper-mcp, perform initialize handshake,
    call search_jobs tool, return the result dict.
    """
    proc = make_mcp_proc()

    try:
        # Step 1: initialize
        init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "linkedin-cv-agent", "version": "1.0"},
            },
        }
        resp = send_recv(proc, init, timeout=30)
        if not resp or "result" not in resp:
            return {"error": "initialize failed", "raw": str(resp)}

        # Step 2: initialized notification
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        proc.stdin.write(json.dumps(notif) + "\n")
        proc.stdin.flush()

        # Step 3: call search_jobs tool
        tool_call = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "search_jobs",
                "arguments": {
                    "keywords": keywords,
                    "location": location,
                    "date_posted": date_posted,
                    "max_pages": max_pages,
                },
            },
        }
        resp = send_recv(proc, tool_call, timeout=timeout)
        if not resp:
            return {"error": "search_jobs timed out"}
        if "error" in resp:
            return {"error": resp["error"]}
        return resp.get("result", {})

    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", required=True)
    parser.add_argument("--location", default="Germany")
    parser.add_argument("--date-posted", default="past_month")
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    result = search_jobs(
        keywords=args.keywords,
        location=args.location,
        date_posted=args.date_posted,
        max_pages=args.max_pages,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
