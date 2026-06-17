import json, sys, io, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

# First run dedup with --force
result = subprocess.run(
    ['python', 'scripts/search_state.py', '--mode', 'dedup',
     '--batch-id', '20260610_001', '--uid', 'leon', '--force'],
    capture_output=True, text=True, encoding='utf-8', errors='replace'
)
print('=== dedup stdout ===')
print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
if result.stderr:
    print('=== dedup stderr ===')
    print(result.stderr[-1000:])
print(f'Return code: {result.returncode}')
