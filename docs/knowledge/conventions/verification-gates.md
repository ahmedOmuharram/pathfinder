---
type: Convention
title: Verification gates
description: The exact commands that decide whether a change is done, for both apps.
tags: [testing, ci, workflow]
generated: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
status: stable
---

Gates passing is necessary, not sufficient: see the definition of done in `CLAUDE.md`. These are the commands.

# Backend (`apps/api`)

```
uv run ruff check src/
uv run ruff format --check src/
uv run mypy --strict src/pathfinder/
uv run pyright src/pathfinder/
uv run lint-imports
uv run pytest src/pathfinder/tests/ -q
```

`pyright` is not redundant with `mypy`: it catches variance and invariance errors mypy misses. `lint-imports` enforces the six layering contracts and is the gate that keeps Domain pure. `ruff format --check` is not redundant with `ruff check` either: the two rule sets do not overlap, and formatting drift is invisible to the linter.

The unit tier refuses every connection made through Python's socket module. An autouse fixture in `src/pathfinder/tests/unit/conftest.py` patches `socket.socket.connect`, `connect_ex`, `socket.getaddrinfo` and the event loop's `create_connection`/`getaddrinfo`, so a stub that no longer covers its seam fails there instead of passing against a live server. The refusal derives from `BaseException`, because every HTTP client here retries under `except Exception` and would otherwise swallow it.

Two limits are worth knowing. The guard runs per test, so anything at collection time is outside it, including the PIGuard and fastembed model downloads the root `conftest.py` performs at import. And a C extension that opens its own socket without going through the `socket` module is not covered.

A unit test that needs a real connection carries `@pytest.mark.allow_network`. No production test does: the two database-backed ones live in `tests/integration/`, where they belong. A new marked test needs a reason, because the marker is how the guard is defeated.

# Frontend (`apps/web`)

```
npx tsc --noEmit
npx eslint src/
node scripts/check-boundaries.mjs
npx vitest run
```

# Mutation testing (`apps/web`)

```
rm -f .stryker-tmp/incremental.json
./node_modules/.bin/stryker run
```

**Delete `incremental.json` first, every time.** The config sets `incremental: true`, and the cache goes stale: it reports mutants that current tests kill as survived. That cost real time once. If a survivor looks impossible, apply the mutation by hand and run the tests before believing the report.

Last full run: 100.00% across the eight `src/state/strategy` modules, zero survivors, zero uncovered.

# Docker

```
docker compose --env-file .env.dev up -d --build --force-recreate api worker
```

`--force-recreate` is not optional. Without it, `up -d --build` can build a new image and leave the old container running, so you verify code that is not deployed. Confirm by grepping for a new symbol inside the container before trusting a manual test.
