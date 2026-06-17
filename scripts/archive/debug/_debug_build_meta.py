import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'scripts')
from pathlib import Path
import search_state

# Simulate what dedup does
search_state.init_paths('leon')
print('OUTPUT_DIR:', search_state.OUTPUT_DIR)

config = json.loads((Path('users/leon') / 'config.json').read_text(encoding='utf-8'))
meta = search_state.build_group_meta(config)

for gid, m in meta.items():
    cv_path = m['cv_parsed']
    skills = search_state.load_cv_skills(cv_path)
    print(f'{gid}: cv_parsed={cv_path} | skills={len(skills)}')
