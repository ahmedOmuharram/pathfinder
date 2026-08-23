---
type: Backlog Item
title: The API lint job is red on two checks CLAUDE.md's documented commands do not run
description: CI runs `ruff check .` and `pip-audit` from apps/api; both fail on paths and packages outside `src/`. Three findings - one S608 in a released migration, one unformatted migration, and 44 known vulnerabilities across 14 third-party packages.
tags: [ci, lint, security, dependencies]
generated: { by: claude-code/opus-5, at: 2026-08-22T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-22T00:00:00Z }
status: stable
---

# What I did

Ran the API lint job's own commands from `apps/api`, not the ones CLAUDE.md
documents (`ruff check src/`):

```
uv run ruff check .
uv run ruff format --check .
uv run pip-audit
```

# What I got

```
S608 Possible SQL injection vector through string-based query construction
  --> alembic/versions/2026_08_19_0001_add_application_id_tenancy.py:77:9
Found 1 error.

Would reformat: alembic/versions/2026_08_09_0001_flush_pre_fbv_checkpoints.py
2 files would be reformatted, 1064 files already formatted

Found 44 known vulnerabilities in 14 packages
click 8.3.2, cryptography 48.0.0, langgraph-checkpoint 4.0.1,
langgraph-checkpoint-postgres 3.0.5, langgraph-sdk 0.3.13, langsmith 0.8.8,
mcp 1.27.0, msgpack 1.1.2, pillow 12.2.0, starlette 1.2.1, ...
pip-audit exit=1
```

`.github/workflows/ci.yml` runs all three in `lint-api`, so the job cannot pass.

# Why that's wrong

The gate reports a colour that nobody reads, so a real finding in `alembic/`
or a real advisory lands in the same output as these three and is invisible.
`langgraph-checkpoint-postgres` and `msgpack` are on the checkpoint path: an
advisory there touches every persisted turn.

# Why it happens

CLAUDE.md documents `uv run ruff check src/`, and `[tool.ruff]` excludes
nothing, so `alembic/` is checked by CI and by nobody else. `pip-audit` has no
ignore list and no dependency bump has followed the advisories.

# Fix

Decide per finding. The S608 builds SQL from a hardcoded table list, so the
honest fix is to stop interpolating rather than to silence it. The formatting
one is `uv run ruff format alembic/`. The advisories need a lock bump with the
checkpoint and Starlette pins verified against a real turn, which is its own
change: `langgraph-checkpoint-postgres` 3.0.5 -> 3.1.1 moves a pinned version.

# What you'd get

`uv run ruff check .`, `uv run ruff format --check .` and `uv run pip-audit`
all exit 0 from `apps/api`, and the next advisory is the only line in the
output.

# Anchor

`.github/workflows/ci.yml` `lint-api`; `apps/api/pyproject.toml` `[tool.ruff]`;
`apps/api/uv.lock`. Done when the three commands exit 0.
