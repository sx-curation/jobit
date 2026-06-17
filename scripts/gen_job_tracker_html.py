#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate C:/Users/Admin/Desktop/job_tracker/index.html from Jinja2 template.

Template:  scripts/templates/index.html
Run:       python scripts/gen_job_tracker_html.py
Then:      python scripts/server.py
"""
import os
from pathlib import Path
import jinja2

SCRIPTS_DIR   = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPTS_DIR / 'templates'
DEST          = Path(__file__).resolve().parent.parent / 'dashboard' / 'index.html'


def generate(dest: Path = DEST) -> Path:
    env  = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )
    tmpl = env.get_template('index.html')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(tmpl.render(), encoding='utf-8')
    return dest


if __name__ == '__main__':
    out = generate()
    size_kb = os.path.getsize(out) // 1024
    print(f'Generated: {out}  ({size_kb} KB)')
    print('Next: python scripts/server.py')
