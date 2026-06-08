#!/usr/bin/env python3
"""One-off: patch duration/city/country into all cv_parsed_*.json for leon."""
import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / 'users' / 'leon' / 'output'

# company name substring → (duration, city, country)
PATCHES = {
    'hapag':      ('12/2024 - 06/2025', 'Hamburg',    'Germany'),
    'ece group':  ('06/2024 - 12/2024', 'Hamburg',    'Germany'),
    'hsbc':       ('01/2021 - 09/2022', 'Guangzhou',  'China'),
    'intelligent power': ('05/2020 - 12/2020', 'Guangzhou', 'China'),
    'grg banking':       ('07/2019 - 12/2019', 'Guangzhou', 'China'),
    'moli media':        ('10/2018 - 07/2019', 'Guangzhou', 'China'),
}

def match(company: str):
    cl = company.lower()
    for key, vals in PATCHES.items():
        if key in cl:
            return vals
    return None

updated = []
for f in sorted(OUTPUT_DIR.glob('cv_parsed_*.json')):
    data = json.loads(f.read_text(encoding='utf-8'))
    changed = False
    for exp in data.get('experience', []):
        patch = match(exp.get('company', ''))
        if patch:
            duration, city, country = patch
            exp['duration'] = duration
            exp['city']     = city
            exp['country']  = country
            changed = True
    if changed:
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        updated.append(f.name)
        print(f'Updated: {f.name}')

print(f'\nDone — {len(updated)} file(s) patched.')
