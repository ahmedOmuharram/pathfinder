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
uv run mypy --strict src/pathfinder/
uv run pyright src/pathfinder/
uv run lint-imports
uv run pytest src/pathfinder/tests/ -q
```

`pyright` is not redundant with `mypy`: it catches variance and invariance errors mypy misses. `lint-imports` enforces the six layering contracts and is the gate that keeps Domain pure.

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
