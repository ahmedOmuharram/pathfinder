---
type: Backlog Item
title: Orphaned steps are deleted before the push that orphans them, so every delete is refused
description: commit.py deletes dropped steps between the step push and the strategy sync. Until the sync runs, WDK's strategy still references them, so the DELETE is refused and the orphans accumulate on the user's account.
tags: [wdk-alignment, strategies, cleanup]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# Symptom

`delete_orphaned_wdk_steps` reports leftovers on every commit that drops a step:

    Some orphaned WDK steps could not be deleted  step_ids=[...]

The warning is logged and the commit proceeds, so nothing surfaces to the user
while their WDK account fills with steps no strategy references.

# Ordering

In `apply_commit` the sequence is:

1. `push_steps_with_plan` -- create/update steps
2. **`delete_orphaned_wdk_steps`** -- delete the dropped ones
3. `sync_strategy_for_site` -- push the new step tree

A step is not orphaned until (3) rewrites the strategy to stop referencing it.
At (2) WDK's copy of the strategy still points at it, so the delete is refused
and the id is dropped from `sync_state.wdk_step_ids` regardless -- the loop pops
the mapping before it attempts the delete. After that commit nothing knows the
step exists, so it is never retried either.

# Fix

Move the delete after the strategy sync, and only drop the local mapping for ids
WDK actually deleted, so a refusal can be retried on the next commit instead of
being forgotten.

# What is not yet established

The refusal code. It was reported as a 409, which is what "still referenced"
should produce, and the code path is consistent with that -- but the status has
not been confirmed against live WDK here. The fix does not depend on which code
it is; the ordering is wrong either way. A live check that would settle it: push
a two-step strategy, drop one step, and record the status of the DELETE issued
before the strategy sync.

# Anchor

`apply_commit` in `services/strategies/commit.py` (the block around
`wdk_ids_to_delete`), and `delete_orphaned_wdk_steps`. Done when a dropped step
is gone from the user's WDK account after one commit, and a refused delete is
retried rather than forgotten.
