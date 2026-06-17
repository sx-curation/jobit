import json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

raw = json.loads(Path('output/temp/raw_results_20260531_001.json').read_text(encoding='utf-8'))
primary = [j for j in raw if j.get('_keyword_type') == 'primary' and j.get('_group_id') == 'group-pdm']
print(f'Primary group-pdm jobs: {len(primary)}')

scored_ids = set()
for d in Path('output').iterdir():
    if d.is_dir() and d.name.startswith('group-pdm_'):
        jd = d / 'jd_analysis.json'
        if jd.exists():
            try:
                data = json.loads(jd.read_text(encoding='utf-8'))
                jid = str(data.get('job_id', ''))
                if jid:
                    scored_ids.add(jid)
            except:
                pass

unscored = [j for j in primary if str(j['job_id']) not in scored_ids]
print(f'Already scored: {len(primary) - len(unscored)}')
print(f'Unscored: {len(unscored)}')
print()
for j in unscored:
    co = (j['company'] or '')[:35]
    ti = (j['title'] or '')[:50]
    kw = (j.get('_keyword') or '')
    print(f"{j['job_id']}  |  {co:<35}  |  {ti:<50}  |  {kw}")

# Also save to temp file for agents
export = []
for j in unscored:
    export.append({
        'job_id': j['job_id'],
        'title': j['title'],
        'company': j['company'],
        'location': j.get('location', ''),
        'url': j.get('url', ''),
        '_keyword': j.get('_keyword', ''),
        'jd': j.get('description_full', '') or j.get('description_snippet', '')
    })
Path('output/temp/_primary_unscored_pdm.json').write_text(
    json.dumps(export, ensure_ascii=False, indent=2), encoding='utf-8'
)
print(f'\nSaved {len(export)} jobs to output/temp/_primary_unscored_pdm.json')
