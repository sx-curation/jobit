"""Remove batch 20260610_001 jobs from seen_jobs so dedup can re-score them correctly."""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

BATCH_ID = "20260610_001"
hist_path = Path('users/leon/output/search_history.json')
h = json.loads(hist_path.read_text(encoding='utf-8'))

# Remove all seen_jobs that were added in this batch
before = len(h['seen_jobs'])
h['seen_jobs'] = {
    jid: info for jid, info in h['seen_jobs'].items()
    if info.get('batch_id') != BATCH_ID
}
after = len(h['seen_jobs'])
print(f"Removed {before - after} entries from seen_jobs (batch {BATCH_ID})")
print(f"Remaining seen_jobs: {after}")

# Reset dedup_done for this batch
for b in h['batches']:
    if b['batch_id'] == BATCH_ID:
        b['dedup_done'] = False
        b['new_total'] = None
        b['displayed'] = None
        print(f"Reset dedup_done=False for batch {BATCH_ID}")

tmp = hist_path.with_suffix('.tmp')
tmp.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding='utf-8')
import os; os.replace(tmp, hist_path)
print("Done. search_history.json updated.")
