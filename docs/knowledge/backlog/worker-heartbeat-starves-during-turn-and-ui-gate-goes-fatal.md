---
type: Backlog Item
title: The worker's heartbeat stalls while a chat turn runs, /health/system reports the worker dead, and every page load shows "Some services failed to start"
description: During a long FRAME (VectorBase, ~6 min) procrastinate_workers.last_heartbeat fell 153 s behind while the worker was actively logging WDK calls. worker_is_alive uses a 30 s window, so /health/system returned workerAlive:false and the web startup gate replaced the whole app with a fatal page ("These subsystems aren't ready: worker") on a fresh navigation. Procrastinate's own stalled-worker timeout is the same 30 s, so the running job is also eligible to be re-run. Since 2026-08-29 a starved heartbeat has a third consequence: the maintenance sweep and Stop fail any job whose worker has been silent past worker_dead_heartbeat_seconds, so a gap that wide would end a live turn. That window is 300 s purely as a margin over the measured 153 s, and fixing this starvation is the prerequisite for lowering it.
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
one after restart) pick the job up again, duplicating a turn. Since 2026-08-29 there is a
third consequence, and it is destructive: `jobs/maintenance.py::release_stalled_jobs`
runs every minute and fails every `doing` job whose worker heartbeat is older than
`worker_dead_heartbeat_seconds`, writing `tool-output-error`, `error`,
`data-turn-failed`, `finish` and `done` into that turn and calling
`finish_job(FAILED)` on it, and `cancel_turn` does the same on Stop. A 153 s gap is
inside the current 300 s window and is safe today; the window is 300 s only because of
this measurement, and it is [the decision that
records it](../decisions/a-dead-worker-fails-its-turn-by-heartbeat.md). Fixing the
starvation is what lets the window drop toward the time a killed worker actually needs
to be noticed.

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
"busy", not "dead"; no duplicate job pickup; and a measured worst-case gap that
`worker_dead_heartbeat_seconds` can follow down from 300 s, so a killed worker's thread
unlocks in a minute rather than in five.
