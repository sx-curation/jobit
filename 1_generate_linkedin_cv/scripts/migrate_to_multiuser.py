#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
One-time migration: copy Leon's existing data into users/leon/ workspace.
Run once from the project root:
    python scripts/migrate_to_multiuser.py

Safe to re-run — skips already-existing targets.
"""
import json, os, shutil, subprocess, sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
USERS_DIR   = PROJECT_DIR / 'users'
USERS_JSON  = PROJECT_DIR / 'users.json'


def _create_junction(link: Path, target: Path):
    """Create Windows junction point (no admin required)."""
    if link.exists() or link.is_symlink():
        print(f"  SKIP junction {link.name} (already exists)")
        return
    if not target.exists():
        print(f"  SKIP junction {link.name} → target not found: {target}")
        return
    result = subprocess.run(
        ['cmd', '/c', 'mklink', '/J', str(link), str(target)],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"  JUNCTION {link.name} → {target}")
    else:
        print(f"  ERROR junction {link.name}: {result.stderr.strip()}", file=sys.stderr)


def _create_hardlink(dst: Path, src: Path):
    """Create hard link (same filesystem, no admin required)."""
    if dst.exists():
        print(f"  SKIP hardlink {dst.name} (already exists)")
        return
    if not src.exists():
        print(f"  SKIP hardlink {dst.name} → source not found: {src}")
        return
    try:
        os.link(src, dst)
        print(f"  HARDLINK {dst.name} → {src}")
    except OSError as e:
        print(f"  ERROR hardlink {dst.name}: {e}", file=sys.stderr)


def _copy_tree(src: Path, dst: Path):
    """Copy directory tree, skip existing files."""
    if not src.exists():
        print(f"  SKIP copy {src.name} (source not found)")
        return
    dst.mkdir(parents=True, exist_ok=True)
    total = 0
    for item in src.rglob('*'):
        if item.is_dir():
            continue
        rel = item.relative_to(src)
        dest_file = dst / rel
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        if dest_file.exists():
            continue
        shutil.copy2(item, dest_file)
        total += 1
        if total % 50 == 0:
            print(f"    copied {total} files…")
    print(f"  COPY {src.name}/ → {dst}  ({total} files)")


def _copy_file(src: Path, dst: Path):
    if dst.exists():
        print(f"  SKIP copy {dst.name} (already exists)")
        return
    if not src.exists():
        print(f"  SKIP copy {dst.name} (source not found)")
        return
    shutil.copy2(src, dst)
    print(f"  COPY {src.name}")


def _create_user_workspace(uid: str, name: str):
    """Create the full workspace for a new user (used by migrate + create-user endpoint)."""
    user_dir = USERS_DIR / uid
    print(f"\n  Creating workspace for user '{uid}' ({name})…")

    # 1. Real directories
    (user_dir / 'output' / 'temp').mkdir(parents=True, exist_ok=True)
    (user_dir / 'my_cv').mkdir(exist_ok=True)
    (user_dir / 'memory').mkdir(exist_ok=True)
    print(f"  MKDIR output/, output/temp/, my_cv/, memory/")

    # 2. Junction points (shared read-only dirs)
    for jname in ['.claude', 'scripts', 'graphify-out']:
        _create_junction(user_dir / jname, PROJECT_DIR / jname)

    # 3. Hard links (shared read-only files)
    for fname in ['SPEC.md']:
        _create_hardlink(user_dir / fname, PROJECT_DIR / fname)

    # 4. Minimal config.json for new (non-migrated) users
    cfg_path = user_dir / 'config.json'
    if not cfg_path.exists():
        template = {
            "job_search": {
                "keyword_groups": []
            },
            "skill_taxonomy": {}
        }
        cfg_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  WRITE config.json (template)")

    return user_dir


def migrate_leon():
    print("=" * 60)
    print("Migrating Leon's data to users/leon/")
    print("=" * 60)

    user_dir = _create_user_workspace('leon', 'Leon')

    # Copy Leon's real data — force-overwrite config (template was written above)
    real_cfg = PROJECT_DIR / 'config.json'
    if real_cfg.exists():
        shutil.copy2(real_cfg, user_dir / 'config.json')
        print(f'  COPY config.json (forced overwrite of template)')
    _copy_tree(PROJECT_DIR / 'my_cv',    user_dir / 'my_cv')
    _copy_tree(PROJECT_DIR / 'output',   user_dir / 'output')
    _copy_tree(PROJECT_DIR / 'memory',   user_dir / 'memory')


def write_users_json():
    if USERS_JSON.exists():
        print(f"\nSKIP users.json (already exists)")
        return
    data = {"users": [{"id": "leon", "name": "Leon"}]}
    USERS_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\nWRITE users.json")


def verify():
    print("\n" + "=" * 60)
    print("Verification")
    print("=" * 60)
    checks = [
        (USERS_DIR / 'leon' / 'config.json',         "leon/config.json"),
        (USERS_DIR / 'leon' / 'output' / 'job_summary.md', "leon/output/job_summary.md"),
        (USERS_DIR / 'leon' / '.claude' / 'agents' / 'Orchestrator.md', "leon/.claude/agents/Orchestrator.md (junction)"),
        (USERS_DIR / 'leon' / 'scripts' / 'check.py', "leon/scripts/check.py (junction)"),
        (USERS_JSON, "users.json"),
    ]
    ok = True
    for path, label in checks:
        status = "OK" if path.exists() else "MISSING"
        if status == "MISSING":
            ok = False
        print(f"  [{status}] {label}")
    if ok:
        print("\nAll checks passed. Ready to restart server.")
    else:
        print("\nSome checks failed — review errors above.", file=sys.stderr)


if __name__ == '__main__':
    migrate_leon()
    write_users_json()
    verify()
    print("\nDone. Restart server: python scripts/server.py")
