#!/usr/bin/env python3
"""Fetch JD texts for 10 specific unanalyzed jobs and write jd_text.txt into folders."""
import json, re, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from common import make_mcp_proc, send_recv

PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR  = PROJECT_DIR / 'users' / 'sara' / 'output'

TARGETS = {
    '4430432128': ('Allegis Group',          'Programmmanager:in'),
    '4428215809': ('HORNBACH Baumarkt AG',    'Business Development Manager (gn)'),
    '4427374486': ('JetBrains',              'Global Workplace Project Manager (m/f/x)'),
    '4426494464': ('JD.COM',                 'E-Commerce Business Development'),
    '4420275667': ('XPO Logistics Europe',   'Business Development Manager Central Europe'),
    '4424589343': ('TUeV NORD GROUP',        'Project Manager Business Field Renewables (m/f/d)'),
    '4430967206': ('Infinity Quest',         'Project Manager'),
    '4428293731': ('Universal Music Deutschland', 'Trainee People Development Talent Acquisition Diversity'),
    '4428086600': ('Lhoist',                 'Associate Director Manager Strategy Commercial Operations'),
    '4385731937': ('Alpitronic',             'Partnership and Relations Manager (m/f/d)'),
}


def slugify(text, max_len=45):
    text = re.sub(r'[^\w\s-]', ' ', str(text))
    text = re.sub(r'\s+', '-', text.strip())
    return re.sub(r'-+', '-', text)[:max_len].rstrip('-')


def extract_jd_text(resp: dict) -> str:
    result = resp.get('result', {})
    sc = result.get('structuredContent', {})
    sections = sc.get('sections', {})

    # Try 'job_posting' or 'about_the_job'
    for key in ('job_posting', 'about_the_job', 'description'):
        if key in sections:
            return sections[key].get('text', '') or sections[key].get('raw_text', '')

    # Fallback: raw_text of full response
    raw = sc.get('raw_text', '')
    if raw:
        return raw

    content = result.get('content', [])
    if content:
        return content[0].get('text', '')
    return ''


def main():
    proc = make_mcp_proc()

    # Initialize
    resp = send_recv(proc, {
        'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
        'params': {'protocolVersion': '2024-11-05', 'capabilities': {},
                   'clientInfo': {'name': 'fetch-10-jds', 'version': '1.0'}},
    }, timeout=30)
    if not resp:
        print('ERROR: MCP init failed', file=sys.stderr)
        return

    proc.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized', 'params': {}}) + '\n')
    proc.stdin.flush()

    for i, (jid, (company, title)) in enumerate(TARGETS.items(), start=2):
        print(f'[{i-1}/10] Fetching {company} ({jid})...')

        resp = send_recv(proc, {
            'jsonrpc': '2.0', 'id': i, 'method': 'tools/call',
            'params': {'name': 'get_job_details', 'arguments': {'job_id': jid}},
        }, timeout=60)

        if not resp or 'result' not in resp:
            print(f'  WARN: no response for {jid}', file=sys.stderr)
            continue

        jd_text = extract_jd_text(resp)
        if not jd_text or len(jd_text) < 50:
            print(f'  WARN: JD text too short ({len(jd_text)} chars) for {jid}')
            # Still write what we have

        folder_name = f'group-innovation_{slugify(company)}_{slugify(title)}_20260621'
        folder = OUTPUT_DIR / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'jd_text.txt').write_text(jd_text, encoding='utf-8')
        print(f'  OK: {folder_name} ({len(jd_text)} chars)')

    proc.stdin.close()
    print('\nDone.')


if __name__ == '__main__':
    main()
