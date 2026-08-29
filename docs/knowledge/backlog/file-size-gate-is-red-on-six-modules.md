---
type: Backlog Item
title: The api file-size gate is red on six modules, so it blocks every api commit
description: check_max_lines.py fails on six modules against a 400-line cap - frame_spec.py (562), strategy.py (472), operations/apply.py (458), mcp/server.py (522), param_dag.py (649) and step_wdk_push.py (416). The gate runs as a pre-commit hook on any api Python change, so it fails for work that touches none of them.
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
6 file(s) exceed 400 meaningful lines:

  FAIL  src/pathfinder/ai/tools/standalone/frame_spec.py: 562 lines (limit 400)
  FAIL  src/pathfinder/ai/tools/standalone/strategy.py: 472 lines (limit 400)
  FAIL  src/pathfinder/domain/strategy/operations/apply.py: 458 lines (limit 400)
  FAIL  src/pathfinder/mcp/server.py: 522 lines (limit 400)
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

Six modules grew past the cap without being added to `EXEMPT_PATTERNS` in
`apps/api/scripts/check_max_lines.py` and without being split. The item was
filed naming two of them; the other four were already red at the time and were
not counted.

# Fix

Split, do not exempt. `param_dag.py` at 649 lines is 249 over the cap, which is
a module doing more than one thing; the exemption list is for pure-model and
single-pipeline files and none of these is one. Take the dependency-walk half of
`param_dag.py`, the WDK-push half of `step_wdk_push.py`, the delete-resolution
half of `operations/apply.py`, the sheet half of `frame_spec.py`, the
edit-tools half of `strategy.py` and the tool-registration half of
`mcp/server.py` into their own modules, keeping every consumer's import name.

# What you'd get

`check_max_lines.py` exits 0, and `file-size-api` fails only when the change
under review is the one that grew a module.
