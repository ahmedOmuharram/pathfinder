---
type: Decision
title: A strategy edit holds the thread's lock across its read
description: POST /operations and POST /insert-saved take the per-thread advisory lock before they read the stored AST and hold it through the WDK round trip and the write, so two overlapping edits cannot each write a whole tree built from the same base; every write of the edit joins that one transaction, and locking only the write, a second session for the consumer record, and compare-and-set on the revision fingerprint were all rejected.
tags: [strategy, persistence, postgres, concurrency, transport]
generated: { by: claude-code/opus-5, at: 2026-08-31T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-31T00:00:00Z }
status: stable
---

# What was decided

`services/conversations/strategy_ops.py::apply_operation` and
`::insert_saved` each open one session, take `pg_advisory_xact_lock` on
`strategy:<conversation_id>`, and hold it for the read of the stored AST, the
in-memory edit, the WDK round trip and the write.
`services/strategies/write_lock.py::strategy_write_scope` is the one place that
decides the transaction of a write: it joins the `locked_session` the context
carries, and takes the lock itself only for a caller that holds none.
`persist_strategy_ast_to_conversation` and
`insert_saved.py::_record_consumer` both go through it.

A graph operation is a read-modify-write of one JSON column: it loads
`conversation_strategies.strategy_ast`, edits the tree in memory, and writes
the whole tree back. The read and the write therefore belong in one lock.
Insert-saved is the same shape with a longer middle: it also reads a saved
strategy from WDK and clones it before it writes.

# Why not lock the write alone

That is what the code did, and it lost edits. Two operations on one thread,
each editing a different step, both read the same base AST; the first commits,
the second writes its own whole tree over it, and the first edit is gone. The
loser is whichever operation reads first and pushes to WDK for longer, so the
observable failure is load-dependent: the same two clicks land under an idle
worker and drop one under a busy one.

`tests/integration/services/conversations/test_concurrent_strategy_edits.py`
holds one writer inside its WDK call while the other reads and commits, in both
directions. Against the write-only lock, a parameter edit to `phosphatase`
reverted a committed `INTERSECT` to `UNION`, a combine-operator edit reverted a
committed `phosphatase` to `kinase`, and an insert-saved held inside its read
of the saved strategy reverted a committed `phosphatase` to `kinase`.

# Why every write of the edit joins the one transaction

Insert-saved records the imported strategy on `conversation_strategies` after
it pushes. Left on a session of its own, that write waits on the row the
caller's own transaction holds while the caller waits for the write to return,
so the request hangs until the statement timeout. There is no second lock to
take and no ordering that helps: a write inside a locked edit belongs to that
edit's transaction.

The cost is that a partial WDK push no longer leaves its half-built tree on
record. `insert_saved_into_conversation` raises on a failed step, the
transaction rolls back, and the thread is exactly as it was; the steps the push
created stay in WDK, referenced by nothing. A retry clones fresh ids anyway, so
nothing in the half-built tree was reusable.

# Why not compare-and-set on the revision fingerprint

`domain/strategy/revision.py::strategy_revision` already fingerprints a tree's
inputs, so the write could refuse when the row moved under it. Refusing turns a
race the user did not cause into an error they have to retry, and the operation
has already pushed to WDK by then, so the refusal leaves WDK ahead of Postgres.
Re-applying the operation to the fresh tree instead would need a second push
plan and a new failure mode when the other writer deleted the step the
operation names. The lock makes the second edit wait and then read the truth,
which is what the researcher expects from two clicks.

# What this costs

One connection stays in a transaction for the length of the WDK push. The lock
is per thread, so it only queues edits to the same strategy, which are already
serial from the researcher's point of view.

# What this does not cover

An agent turn reads the strategy into `AgentDeps.strategy_session` when the turn
opens and writes it when a tool commits, minutes apart. No lock is held across
that window, so a user edit made mid-turn can still be overwritten by the turn's
own write. That is the merge rule in
`persist.py::_merge_agent_ast_into_current` ("the agent owns the graph
topology"), not a race this decision closes.
