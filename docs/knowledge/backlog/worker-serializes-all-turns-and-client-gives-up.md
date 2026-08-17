---
type: Backlog Item
title: A queued or long-running turn's SSE response carries no heartbeat or "queued" event, so the client reports "Failed to fetch" while the server keeps going and a retry queues a duplicate turn
description: The worker now runs WORKER_CONCURRENCY jobs (default 4) with per-conversation serialization, so unrelated conversations no longer wait on each other; but a turn that is queued behind the same conversation's previous job, or a long running turn, still streams nothing until chunks arrive. A PlasmoDB tab showed "Thinking..." with no chunks and then "Response failed / Failed to fetch" while the turn ran anyway; the result appeared only after a reload.
tags: [investigation, ui-run, jobs, worker, sse, ux]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, two tabs: PlasmoDB and VectorBase)

**What I did.** Sent a long VectorBase prompt (midgut proteases, transform, colocation)
in one tab, then ~30 s later a PlasmoDB prompt (scored variant comparison) in another tab,
same user. At the time the worker ran one job at a time; that half is fixed (see below).

**What I got.** api log: `Deferred 1 job` at 15:50:58 for the PlasmoDB turn (`POST
/api/v1/chat 200`). worker log: `Starting job chat_turn:run[1379]` (VectorBase) ...
`chat turn completed` 15:56:08, then the PlasmoDB conversation's checkpoint deserialisation
at 15:56:09. In the PlasmoDB tab: "Thinking..." with the token counter frozen at 635.6K
for ~2 min, then "Response failed - Failed to fetch - Try again". After a reload the turn's
full output was there (it had run 15:56 onward).

**Second drop, running not queued (VectorBase, conversation 762c33a2).** During a
running clarification turn (frame at 148.9K tokens and climbing) the tab showed "Response
failed - network error"; the worker log later printed "chat turn completed" for that turn
and a reload showed the full result. So the client-side stream also dies during long
running turns, not only while queued.

**Why that is wrong.** The client turns a wait into a failure message while the server
keeps going, so a user who presses "Try again" queues a duplicate turn; a long durable
enrichment (3.5 min measured) still delays the same conversation's next turn with no
indication.

**Why it happens.** The SSE response for `POST /api/v1/chat` carries no heartbeat or
"queued" event while the job waits or while a long step produces no chunks, so the Next
proxy / browser gives up; the client has no queued state.

**Already fixed.** `jobs/worker.py:amain` passes `concurrency=WORKER_CONCURRENCY`
(default 4; procrastinate 3.8.1 has one global concurrency, no per-queue setting), and
chat-turn and durable-tool jobs are deferred with `lock=<conversation_id>` so only jobs of
the same conversation serialise.

**Fix (to decide).** Emit a `data-turn-status {label: "Queued", position}` chunk while
the job is pending and keep the SSE alive with comment frames during long silent steps;
on the client, render Queued and do not convert a still-pending stream into "Failed to
fetch".

**What you would get.** If a wait is unavoidable the user sees "Queued (1 ahead)" and the
stream stays connected until the turn starts and while it runs.
