---
type: Decision
title: A durable tool is a deferred tool, so its completion continues the turn instead of replaying it
description: "@durable_tool creates the background_tasks row, defers the job, records the deferral on the deps and raises CallDeferred; the run ends with the call parked on the state and the worker opens a NEW turn carrying DeferredToolResults for that tool_call_id. LangGraph interrupt() inside the node was rejected: a resume re-executes the node from its first line, so every model call and tool side effect before the interrupt runs again."
tags: [durable-tasks, resume, langgraph, pydantic-ai, assistant-core, protocol]
generated: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
status: stable
---

# What was decided

A durable tool ends its run the way an approval does. `@durable_tool` creates
the `background_tasks` row (which now records the pydantic-ai `tool_call_id`
the result will answer), defers the procrastinate job, records a
`DurableDeferral` on the agent's deps, writes `data-background-task-started`
through the graph's stream writer, and raises `CallDeferred`. The run's output
is `DeferredToolRequests`, the turn parks a `PendingDurableCall` on the state
beside `pending_approval`, and the turn closes with `finishReason: "other"`.

When the job finishes, the worker announces `data-task-completed` and then
opens a NEW turn on the thread with `TurnRequest(durable_result=...)`. That
turn resumes the parked run from `prior_messages_json` with
`DeferredToolResults(calls={tool_call_id: ToolReturn(...)})`. The tool's
declared `chunks_from_result` runs there and rides the result's `metadata`, so
its summary and figure land beside the tool's output part, in the position the
adapter already emits metadata chunks. A durable call inside a sub-agent parks
the dispatch call with the sub-agent's `messages_json`, and the completion turn
re-enters that run first, exactly as an approval does.

# What was rejected

**LangGraph `interrupt()` inside the node.** The tool called `interrupt()` from
inside the agent run, inside the `lead` node, and the worker resumed with
`Command(resume=...)`. LangGraph's contract is that a resume re-executes the
node from its first line and matches resume values to `interrupt()` calls by
their order in the node. The whole Lead run therefore started over: the model
was called again, tool side effects before the durable call ran again, and the
stored result was handed to whichever call the replay reached. Measured on the
febrile-versus-normal DESeq prompt: one prompt produced two EDA analyses, three
compute jobs, two `create_eda_step` failures and a turn that never wrote
`done`.

**A per-task resume channel.** Delivering the result into the suspended call in
place would need the in-flight run to live somewhere durable. The deferred-tool
cycle already parks a run and re-enters it, so a second mechanism beside it
would be two ways to say the same thing.

# What the migration costs

`2026_08_30_0001` adds `background_tasks.tool_call_id` and flushes every
checkpoint, because the state shape gained the parked durable call and a strict
state does not read an older shape - not only the threads that were
interrupted. On the dev database that meant 17 threads, one of them
interrupted. A flushed thread loses its graph state (the operational spec, the
last build outcome, the verification digest, retrieved memories), any pending
approval, its turn token and cost totals, and a one-agent thread's
`thread_messages_json`; it keeps its conversation row, every chunk in
`conversation_events`, its `messages` rows, its strategy and its
`background_tasks`. The next turn on such a thread reconstructs its spec from
the persisted AST and reads its transcript from the log.
`decisions/no-checkpoint-truncation.md` records the same practice and the
reasoning that settled it.

# What follows

`_resume_graph`, `Command(resume=...)`, `_interrupt_chunks` and the
`interrupt` import are gone; `grep -rn "interrupt(" src/pathfinder` finds no
durable use. The observable wire is unchanged, so PROTOCOL 6.1 stands as
written: the started chunk inside the suspending turn, progress and completion
in the gap, and the continuation as a turn with its own `start`, `finish` and
`done`.

A parked call is thread state. `fork_conversation` copies checkpoints
verbatim (`copy_checkpoint_state`), so a branch taken while a durable task
is running would carry a `pending_durable_call` naming a task whose
completion turn opens on the parent thread only; the branch would hold a
call nothing answers. Not yet reproduced; the fork cards in the backlog
(`fork-log-rows-cascade-with-the-parents-task-rows`, `fork-drops-the-assistant-id`)
are where a fork that clears or re-parks the call belongs.
