---
type: Backlog Item
title: The api file-size gate is red on two service modules, so it blocks every api commit
description: check_max_lines.py fails on services/catalog/param_dag.py (649 lines) and services/strategies/step_wdk_push.py (416) against a 400-line cap. The gate runs as a pre-commit hook on any api Python change, so it fails for work that touches neither file.
tags: [verification-gates, pre-commit, services, refactoring]
generated: { by: claude-code/opus-5, at: 2026-08-25T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-25T00:00:00Z }
status: stable
---

# What I did

```
cd apps/api && uv run python scripts/check_max_lines.py
```

# What I got

```
  FAIL  src/pathfinder/services/catalog/param_dag.py: 649 lines (limit 400)
  FAIL  src/pathfinder/services/strategies/step_wdk_push.py: 416 lines (limit 400)

Fix by splitting into smaller modules.
```

Exit code 1, on a tree where neither file was edited.

# Why that's wrong

`file-size-api` in `.pre-commit-config.yaml` runs on `^apps/api/.*` for any
Python change, with `pass_filenames: false`. So the gate fails for a change that
touches only tests, only a router, or only a workflow, and the two names it
prints are not the change under review. A gate that is red for everyone is a
gate everyone learns to pass with `--no-verify`, and then it stops catching the
file it was written for.

# Why it happens

Both modules grew past the cap without being added to `EXEMPT_PATTERNS` in
`apps/api/scripts/check_max_lines.py` and without being split.

# Fix

Split, do not exempt. `param_dag.py` at 649 lines is 249 over the cap, which is
a module doing more than one thing; the exemption list is for pure-model and
single-pipeline files and neither of these is one. Take the dependency-walk half
of `param_dag.py` and the WDK-push half of `step_wdk_push.py` into their own
modules, keeping every consumer's import name.

# What you'd get

`check_max_lines.py` exits 0, and `file-size-api` fails only when the change
under review is the one that grew a module.
