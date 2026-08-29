---
type: Backlog Item
title: The Playwright no-first-nth gate is red on 16 escapes in six older specs
description: apps/web/scripts/check-no-first-nth.mjs exits 1 on 16 uses of .first(, .nth( or .last( without a TODO(weak-strict-mode) marker, in cross-feature/gene-set-analysis-pipeline (7 across the two cross-feature specs), feature/branch-switch (3), feature/durable-verification (1), feature/experiment-flows (2), feature/fork-branch (2) and feature/parameter-sweep (1); measured on 2026-08-29 during EDA batch 7, whose three new specs and fixture contribute none. Every plan ladder lists this gate, so a red trunk hides a new escape.
tags: [e2e, playwright, gates]
generated: { by: claude-code/fable-5, at: 2026-08-29T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-29T00:00:00Z }
status: stable
---

**What I did.** Ran `node scripts/check-no-first-nth.mjs` from `apps/web`
during the batch-7 ladder, twice.

**What I got.** Exit 1 with the same 16 escapes both times, none in
`e2e/feature/eda-*.spec.ts` or `e2e/fixtures/eda.ts`.

**Why that is wrong.** A gate that is red on the trunk cannot catch a new
index-based locator, and an index-based locator is how a strict-mode
collision gets hidden instead of fixed.

**Why it happens.** The six specs predate the gate.

**Fix.** Replace each escape with a specific locator (the precedent is
`GraphPage.firstRailStepId` in `e2e/pages/graph.page.ts`, which reads ids
out of the DOM with `evaluateAll`), or justify the rare real ambiguity with
the marker the script accepts; then put the script in CI.

**What you would get.** A green gate that fails only on a new escape.
