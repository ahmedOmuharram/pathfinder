---
type: Decision
title: A memory-store call is bounded by the turn, and the two calls fail differently
description: Retrieval at Lead entry and the auto-write in finalize_turn run under memory_store_timeout_seconds (default 30); exhaustion raises MemoryStoreTimeoutError, which retrieval logs and degrades to no memories while the auto-write re-raises into the turn's error path. An unbounded await was measured parking a test run for the full 600 s ceiling. The store's batch task is also ended with the store, so a closed store leaves nothing pending.
tags: [memory, langgraph, jobs, worker, reliability, chat]
generated: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
status: stable
---

# What was decided

A turn touches the LangGraph store twice: `ai/graph/_lead_turn.py::retrieve_memories`
at Lead entry and `auto_write_memories` in `finalize_turn`. Both now run inside
`assistant_core.memory.deadline.memory_store_deadline`, an `asyncio.timeout`
whose window is `memory_store_timeout_seconds` (default 30). Exhaustion raises
`MemoryStoreTimeoutError`, which carries the operation and the window.

The two calls answer it differently, because they are worth different things.
**Retrieval degrades**: it logs a warning naming the thread and returns `[]`,
and the turn runs on the user's prompt alone. **The auto-write fails loudly**:
it logs and re-raises, so `run_turn` writes `error`, `data-turn-failed`,
`finish` and `done`, and the user sees a turn that ended. A memory the user
believes was saved and was not is worse than a turn that says it broke.

`MemoryStoreTimeoutError` is caught before the `(RuntimeError, ValueError,
OSError, SQLAlchemyError)` handler that already swallowed auto-write failures;
it subclasses `TimeoutError`, which is an `OSError`, so the order is what keeps
it loud.

# Why the store was the call that could hang

Every other outbound call of a turn is bounded: the WDK client sets
`httpx.Timeout` (30 s per component request, 120 s to the portal), the
embeddings client sets 60 s with five retries, and the model clients carry the
provider default. The store did not. `AsyncBatchedBaseStore.aget/asearch/aput`
put an operation on a queue and `await` a future that only the background batch
task resolves, and `AsyncPostgresStore.from_conn_string` opens one plain
`AsyncConnection` with no statement timeout, so a connection that stops
answering parks the turn with nothing to end it.

Measured: `tests/unit/ai/graph/test_memory_deadline.py`, written against a
store whose `asearch` never resolves, ran for the full 600 s command ceiling
before the deadline existed and finishes in 1.26 s with it. The backlog item
this closes recorded turns of 939 s, 1039 s and 1909 s against a 12.7-29.6 s
normal band for the same prompt.

# The batch task ends with the store

`lifespan_memory_store` is a per-turn `async with`, and the store's background
batch task was not part of it: `AsyncBatchedBaseStore` cancels the task only
from `__del__`, so every turn left a task the loop reported as
"Task was destroyed but it is pending" at `langgraph/store/base/batch.py:330`,
which is the line the backlog item quoted. The lifespan now cancels and awaits
that task before the connection closes, so the store owns its task for exactly
as long as the turn owns the store. The task is private to LangGraph and there
is no public shutdown, which is why `_task` is read directly.

# What was rejected

**One long-lived store per worker process.** It would remove the per-turn
`setup()` round trip, but it also keeps one Postgres connection open across
turns, and a connection that dies quietly is the failure this item is about. A
per-turn store gets a fresh connection every turn, and the deadline covers the
turn that is unlucky.

**Bounding the store inside `MemoryStore`.** The wrapper would then own a
policy that differs per call site: retrieval degrades and the auto-write does
not. The deadline sits where the decision about the failure is made.

**Letting the auto-write degrade like retrieval.** The turn would report
success while silently keeping no memory of it, and the next turn would
re-derive the same candidate and fail the same way, with nothing on screen
either time.
