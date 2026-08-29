---
type: Decision
title: A dead worker fails its turn by heartbeat, at five minutes of silence
description: The maintenance sweep releases the jobs of a worker whose heartbeat is older than 300 s as well as the jobs past the started-age timeout, Stop releases the same job on the spot, and a released turn closes its open tool calls first; a 60 s window was rejected because a live worker was measured 153 s behind, and the age timeout alone because it leaves a locked thread for an hour after an out-of-memory kill.
tags: [jobs, procrastinate, chat, worker, reliability, protocol]
generated: { by: claude-code/opus-5, at: 2026-08-29T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-29T00:00:00Z }
status: stable
---

# What was decided

A chat turn runs on the worker. When the kernel kills that worker, the turn's
procrastinate job stays in `doing` on a worker id that will never report again,
holding `lock=<conversation id>`, and the thread's newest chunk is whatever the
turn had written. Three rules now end that turn.

**The sweep names a dead worker by its heartbeat, after five minutes of
silence.** `jobs/maintenance.py::release_stalled_jobs` asks the job manager
twice: once with `seconds_since_heartbeat=worker_dead_heartbeat_seconds`
(default 300, minimum 60), which reads `procrastinate_workers.last_heartbeat`,
and once with the deprecated `nb_seconds=worker_stalled_job_timeout_seconds`
(default 3600), which reads the job's `started` event. The two sets are merged
by job id and the heartbeat reason wins. The sweep is `cron="* * * * *"`, so a
killed worker loses its turn five to six minutes after it dies, instead of an
hour later.

**Stop does not wait for the sweep, once the worker is that quiet.**
`cancel_turn` and `cancel_active_turn` write the cancel request a live worker
polls, then call `release_dead_turn(conversation_id)`, which releases the
conversation's chat-turn job through the same `release_job` the sweep uses,
and only when that job's worker has been silent past the same 300 s. A cancel
request is a row; a dead worker reads no rows, so without this the user's Stop
changed nothing on screen. A worker that died more recently than the window
still owns its turn, and Stop leaves the request for the sweep.

**A released turn closes its tool calls before its terminator.**
`assistant_core.conversation.open_tool_calls` reads the turn's own chunks and
writes one `tool-output-error` per call that carries an input and no result,
before `error`, `data-turn-failed`, `finish` and `done`. The turn runner does
the same from an in-memory tracker when its own driver raises.
`PROTOCOL.md` 1.3.1 states the rule, so a client never renders a running tool
call inside a finished turn.

# The two heartbeat windows, and what each one means

`procrastinate_workers.last_heartbeat` is read by two rules with different
consequences, and neither number is the other's.

| Window | Where | Meaning |
| --- | --- | --- |
| 30 s | `platform/health.py::WORKER_HEARTBEAT_MAX_AGE_SECONDS` | `/health/system` reports `workerAlive:false`. A warning about responsiveness. Nothing is failed. It matches procrastinate's own `stalled_worker_timeout`. |
| 300 s | `worker_dead_heartbeat_seconds` | The sweep and Stop fail the jobs that worker holds and release their locks. Destructive: the turn ends with an error. |

The health window stays at 30 s. Reporting "not heartbeating" early is useful;
failing a turn early is not the same act and does not get the same number.

# What it looked like without this

One prompt on plasmodb called `search_eda_studies`. The worker
(`mem_limit: 2g`) built the EDA study index cold, docker reported `oom` and
`die 137` on `pathfinder-worker-1` 49 seconds after the call, and the worker
restarted. The job stayed `status=doing` on the dead worker id, holding the
conversation lock, and the thread's newest chunk stayed
`tool-input-available`, so the card read "Running" with no end. The user's
Stop wrote a cancellation row that only a live worker reads.

# Why not a 60 s window

Because a live worker was measured 153 s behind. During a VectorBase FRAME of
about six minutes, with the worker actively logging WDK calls,
`procrastinate_workers.last_heartbeat` was 153 s old
([the starvation item](../backlog/worker-heartbeat-starves-during-turn-and-ui-gate-goes-fatal.md)).
The heartbeat coroutine shares the event loop with up to
`WORKER_CONCURRENCY` jobs, and concurrent turns starve it more, not less. A
60 s window would have written `tool-output-error`, `error`, `finish` and
`done` into that healthy turn and called `finish_job(FAILED)` on a job still
executing: the user would watch a working answer turn into a failure. 300 s is
the same floor the age timeout already uses and about twice the worst measured
gap.

**Lowering it is gated on the starvation fix, not on judgement.** When the
heartbeat runs where a job cannot starve it, the worst gap becomes a measured
number again and this window can follow it down. Until then the margin is the
only thing separating a dead worker from a busy one.

# Why not the started-age timeout alone

That is what [the 2026-08-17 entry](../log.md) chose, and its reason still
holds: the sweep was built on the job's `started` event "and not the
heartbeat, because a starved loop can self-prune a live worker's row". It was
right about the hazard and it is why the window here is 300 s and not 30 s.
What it does not cover is the case that started this work.
`worker_stalled_job_timeout_seconds` defaults to 3600 with a floor of 300, and
it measures how long a job has been running, not whether anything is running
it. After an out-of-memory kill the thread stays locked and the card stays
"Running" for an hour. Lowering that number is not a substitute either: it is
the same number for "this worker is gone" and "this turn is taking too long",
and a legitimate turn with a durable verification tool runs for many minutes
on a worker that answers. The heartbeat answers the first question and the age
timeout answers the second, which is why both run.

# Why not have the API notice the dead worker

The API could watch heartbeats itself, but it would be a second implementation
of a state procrastinate already publishes in `procrastinate_workers`, and it
would have to duplicate the write of the turn's terminator. The cancel path
calls into `jobs/maintenance.py` instead, so there is one `release_job`, one
terminator sequence and one error text.

# Only the api writes the study index

`EMBEDDING_INDEX_SYNC_ENABLED=false` on the worker and on `wdk-mcp`, beside the
`CATALOG_REFRESH_ENABLED=false` that already keeps them from rebuilding a stale
WDK catalog. A process with the flag false never calls
`assistant_core/embeddings/record_manager.py::sync_index`; it searches what the
api wrote. A study search over an index with no membership rows degrades to a
name match with guidance rather than writing, so a turn never blocks on a sync.

The reason was measured when the index was a local model writing a file, and
the numbers are kept as history. Two processes encoding one store starved each
other: a 20-text probe took 1.170 s per text while the api was encoding against
0.485 s per text alone, the api's own encode took 704.7 s contended against
372.6 s clear, and one api warm-up and one worker build left running together
made almost no progress for over an hour.

Since [embeddings are an API call and a Postgres record
manager](embeddings-are-an-api-and-a-record-manager.md) the contention is gone -
the whole study index syncs in 3.7 s and a warm sync embeds nothing - so the
flag now buys a single writer rather than throughput. The retry this guard used
to cost a turn in the minutes after a deployment is gone with it: the api's
warm-up fills the index before it binds anything a turn reaches.
