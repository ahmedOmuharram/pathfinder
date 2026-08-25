---
type: Backlog Item
title: A parameter sweep's per-variant progress collapses to one lane on the thread
description: Every variant of a sweep emits `data-task-progress` under the same `id` (the task id), so the reconciliation rule of PROTOCOL 5.2 keeps one part for the whole fan-out. The card that now reads the thread can show one bar where the sweep runs N trials, and the bar jumps between variants.
tags: [web, protocol, tasks, sweep]
generated: { by: claude-code/opus-5, at: 2026-08-25T00:00:00Z }
status: stable
---

# What I did

Read what reaches the thread while `optimize_search_parameters` runs a fan-out,
after the task card was moved onto the message's own parts.

# What I got

`optimize_params_impl.py:171` derives one child emitter per variant
(`progress.scoped(variantId=v.id)`), and every child shares the parent's
thread log (`jobs/progress.py:128`, `child._thread_log = self._thread_log`).
Each update is written with `task_progress_event(task_id=self.task_id, ...)`,
which sets `id=str(task_id)` (`assistant_core/graph/stream_events.py:47`) for
every variant.

The reducer keys a data part on its type and its `id`
(`packages/assistant-client-ts/src/core/reduce.ts:135-145`), so a five-variant
sweep leaves exactly one `data-task-progress` part on the message: the last
update written, whichever variant produced it.

# Why that's wrong

The bar reports one variant at a time and moves backwards when the next
variant's update lands (variant B at 50 percent, then variant A at 33). A
researcher watching a sweep cannot tell how many trials are running or how far
the sweep as a whole has gone.

# Why it happens

The `id` names the task, not the lane. PROTOCOL 6.1 states that
`data-task-progress` carries the task id as its `id`, so the collapse is what
the protocol currently specifies, not a client defect.

# Fix

Give a scoped emitter a lane id: emit `id=f"{task_id}:{variant_id}"` when the
update carries a scope, keep the bare task id when it does not, and say so in
PROTOCOL 6.1 (a client reads the lane from `toolSpecific.variantId`, which the
payload already carries). Then the reducer keeps one part per lane and the card
renders one row per variant. This is a protocol edit plus
`assistant_core/graph/stream_events.py` and `jobs/progress.py`; the web side is
a list instead of a single chunk.

# What you'd get

A sweep of five variants leaves five progress parts on the message, one per
lane, each advancing on its own, and the card renders five rows that survive a
reload.
