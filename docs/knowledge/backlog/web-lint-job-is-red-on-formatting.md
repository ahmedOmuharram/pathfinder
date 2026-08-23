---
type: Backlog Item
title: The web lint job is red on a formatting check CLAUDE.md's documented commands do not run
description: CI runs `yarn format:check` in lint-web and 645 files fail it. The source was wrapped at a narrower column than the `printWidth: 88` the config declares, so prettier rejoins lines nothing is wrong with, and the job cannot pass.
tags: [ci, lint, web, formatting]
generated: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
status: stable
---

# What I did

Ran the web lint job's own commands from `apps/web`, not the four CLAUDE.md
documents (`tsc --noEmit`, `eslint src/`, `check-boundaries.mjs`, `vitest run`):

```
yarn format:check
```

# What I got

```
Code style issues found in 645 files. Run Prettier with --write to fix.
```

One example, `src/state/strategy/useStepSnapshot.ts`, which no recent change
touched:

```
line 87 (23 chars):       const lifecycle =
line 88 (69 chars):         step !== null ? state.stepLifecycleById[step.id] : undefined;
```

Prettier joins those into one 85-character line, because `.prettierrc.json`
declares `"printWidth": 88`.

# Why that's wrong

`.github/workflows/ci.yml` runs `yarn format:check` as the second step of
`lint-web`, so that job cannot pass on any pull request that touches the web
tree. A gate that is always red is a gate nobody reads, and it hides the day a
real formatting mistake lands. It also puts a trap under every change: the
`prettier-web` pre-commit hook runs `yarn format`, which writes, so a commit
that touches one file can rewrite hundreds and bury the change it carried.

# Why it happens

The tree was wrapped at a narrower column than the config declares - the joined
lines all fit inside 88 - so the two disagree everywhere at once rather than in
a few places. Nothing enforces the check locally: the documented frontend
commands do not include it, and the pre-commit hook writes instead of checking.

# Fix

Run `yarn format` once over `apps/web` as its own change that touches nothing
else, so the reformat is reviewable on its own and never rides along with
feature work. Then add `yarn format:check` to CLAUDE.md's frontend command list
so the gate is one people run, and consider a `--check` pre-commit hook so a
drift is reported rather than silently written.

# What you'd get

`yarn format:check` green, `lint-web` able to pass, and a commit that touches
one component showing one component in its diff.
