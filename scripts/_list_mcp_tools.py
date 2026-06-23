#!/usr/bin/env python3
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from common import make_mcp_proc, send_recv

proc = make_mcp_proc()
send_recv(proc, {'jsonrpc':'2.0','id':1,'method':'initialize',
    'params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'debug','version':'1.0'}}}, timeout=30)
proc.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized','params':{}}) + '\n')
proc.stdin.flush()

resp = send_recv(proc, {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}}, timeout=30)
if resp:
    tools = resp.get('result', {}).get('tools', [])
    print(f'{len(tools)} tools available:')
    for t in tools:
        print(f"  {t['name']}: {t.get('description','')[:80]}")
else:
    print('No response')
proc.stdin.close()
