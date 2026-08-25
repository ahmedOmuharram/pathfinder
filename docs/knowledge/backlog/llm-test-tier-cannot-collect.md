---
type: Backlog Item
title: The opt-in llm test tier cannot even collect, and no ladder notices
description: tests/llm/conftest.py:23 imports ClarificationQuestion, a symbol deleted from ai/graph/state.py in an earlier change, so opting in (pytest --override-ini addopts='' src/pathfinder/tests/llm) dies at collection. Every ladder excludes the tier (pyproject addopts ignores tests/llm and deselects -m llm), so the breakage is invisible to CI and to every gate run. Fix: repair or delete the tier; if it stays, add a collection-only smoke (pytest --collect-only on the tier) to a ladder so an opt-in tier can never silently rot again.
tags: [tests, gates, llm]
generated: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
status: stable
---

**What I did.** Ran the llm tier with the addopts exclusion overridden
(2026-08-24, batch A review).

**What I got.** Collection error: tests/llm/conftest.py:23 imports
ClarificationQuestion from pathfinder.ai.graph.state, which no longer
defines it.

**Why that is wrong.** An opt-in tier that cannot collect is dead weight
that looks like coverage; anyone opting in to run it gets an import error
instead of tests, and no gate reports the rot.

**Why it happens.** The tier is excluded from every ladder by
pyproject addopts, so symbol deletions never break a visible run.

**Fix.** Repair the import or delete the tier; either way, add a
collection-only smoke for opt-in tiers to a ladder.

**What you would get.** Opt-in tiers that either run or do not exist.
