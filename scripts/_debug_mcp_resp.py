#!/usr/bin/env python3
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
from common import make_mcp_proc, send_recv

proc = make_mcp_proc()
send_recv(proc, {'jsonrpc':'2.0','id':1,'method':'initialize',
    'params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'debug','version':'1.0'}}}, timeout=30)
proc.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized','params':{}}) + '\n')
proc.stdin.flush()

resp = send_recv(proc, {
    'jsonrpc':'2.0','id':2,'method':'tools/call',
    'params':{'name':'get_job_details','arguments':{'job_id':'4430432128'}},
}, timeout=60)

print(json.dumps(resp, ensure_ascii=False, indent=2)[:6000])
proc.stdin.close()
