---
type: Backlog Item
title: The worker's heartbeat stalls while a chat turn runs, /health/system reports the worker dead, and every page load shows "Some services failed to start"
description: During a long FRAME (VectorBase, ~6 min) procrastinate_workers.last_heartbeat fell 153 s behind while the worker was actively logging WDK calls. worker_is_alive uses a 30 s window, so /health/system returned workerAlive:false and the web startup gate replaced the whole app with a fatal page ("These subsystems aren't ready: worker") on a fresh navigation. Procrastinate's own stalled-worker timeout is the same 30 s, so the running job is also eligible to be re-run.
tags: [investigation, ui-run, jobs, worker, health, availability]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17)

**What I did.** While a VectorBase turn was in its frame (worker log streaming
"Site-search lookup failed; falling back to discovery search" and WDK calls), opened
`/plasmodb/conversation` in another tab and typed `/help`.

**What I got.** The page rendered only: "Some services failed to start. These subsystems
aren't ready: worker. Please report this to an administrator."
`GET /health/system -> {"ready":false,"apiReady":true,"workerAlive":false,
"notReady":["worker"]}`. `docker compose ps`: worker Up 3 hours. In the database:
`procrastinate_workers` newest `last_heartbeat` = 16:15:42 UTC, age 153 s, while the
worker log for the same minutes shows the frame's WDK traffic.

**Why that is wrong.** The product goes fully dark for every user whenever one turn runs
long, which is exactly when users are waiting on it; the message blames an outage that is
not happening. Because Procrastinate uses the same 30 s window
(`stalled_worker_timeout`), a stalled heartbeat can also let a second worker (or the same
one after restart) pick the job up again, duplicating a turn.

**Why it happens.** The worker runs up to `WORKER_CONCURRENCY` jobs (default 4,
`jobs/worker.py:amain`) on one event loop and the heartbeat coroutine shares that loop;
a turn's work starves it long enough to miss several 10 s beats, and several concurrent
turns starve it more, not less. Whether the
starvation is a blocking call (embedding, sync I/O) or scheduler pressure is not yet
measured. `platform/health.py:worker_is_alive` treats a stale heartbeat as dead, and the
web gate treats "not ready" as fatal rather than degraded.

**Fix (to decide).** Measure what blocks the loop during a frame (a `loop.slow_callback_duration`
run or a heartbeat-gap log). Then: run the heartbeat where a job cannot starve it (a
dedicated task with its own DB connection, or a separate lightweight process), raise
`WORKER_HEARTBEAT_MAX_AGE_SECONDS` above the worst measured gap while keeping it below
Procrastinate's stalled timeout, and change the web gate to a non-blocking banner
("background worker unresponsive; turns may queue") for the worker case.

**What you would get.** A long turn no longer takes the app down; the health page says
"busy", not "dead"; no duplicate job pickup.
