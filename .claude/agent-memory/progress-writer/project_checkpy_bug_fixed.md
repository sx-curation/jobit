---
name: scripts/check.py semicolon bug — fixed in Session #4
description: Two bugs in check.py where continue/return were on the same line as if verbose: causing them to only execute in verbose mode — both fixed
type: project
---

scripts/check.py had two bugs where `continue` (line 105) and `return` (line ~130) were written on the same line as `if verbose:` using a semicolon. This caused those control-flow statements to only execute when `verbose=True`, breaking normal (non-verbose) mode.

**Why:** The bug caused a FileNotFoundError crash on `output/cv_parsed_group-pdm.json` when running sanity check without `--verbose`. Fixed in Session #4 (2026-04-06).

**How to apply:** Both bugs are now fixed. If check.py behaves differently between verbose and non-verbose modes in the future, suspect the same pattern.
