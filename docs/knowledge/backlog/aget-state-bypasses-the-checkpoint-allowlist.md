---
type: Backlog Item
title: Reading a thread with graph.aget_state decodes checkpoint values outside the msgpack allowlist, so every allowlisted type still prints the deprecation warning
description: The chat debugger's `respond` path and the eval runner both read a finished thread through `graph.aget_state`, and both print "Deserializing unregistered type ..." for MemoryValue, TextUIPart, StrategyDomainState, PhaseDisposition and CombineOp - types that are on the allowlist `assistant_core.conversation.serde` builds. The same checkpoint decoded by `astream` during a second turn prints nothing. When LangGraph makes unregistered types an error, the read path breaks while the turn path keeps working.
tags: [investigation, assistant-core, checkpointer, langgraph, ws-v]
generated: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
status: stable
---

# Investigation (2026-08-23, api container, mock provider)

**What I did.** Drove one mock turn on a fresh thread
(`pathfinder.devtools.chat run "Build a comprehensive kinase strategy for
Plasmodium." --site plasmodb --mock --quiet --conversation-id <id>`), then drove
a second turn on the same thread, then read the same thread's state through
`pathfinder.devtools.chat._gate_from_checkpoint`, which opens
`lifespan_checkpointer(url, checkpoint_types=registry.checkpoint_types())` and
calls `graph.aget_state`.

**What I got.** The second turn printed **zero** lines matching
`Deserializing unregistered`. The `aget_state` read printed **eleven**, naming
`pathfinder.domain.strategy.ops.CombineOp`,
`pathfinder.ai.graph.state.PhaseDisposition`,
`pathfinder.ai.graph.state.StrategyDomainState`,
`pydantic_ai.ui.vercel_ai.request_types.TextUIPart` and
`assistant_core.memory.schemas.MemoryValue` (seven times).

`MemoryValue` and `TextUIPart` are in `CORE_CHECKPOINT_TYPES`.
`StrategyDomainState` is in `PATHFINDER_CHECKPOINT_TYPES`. All three are on the
allowlist that the serializer is built from, and all three warn anyway.

**Why that's wrong.** `assistant_core/conversation/serde.py` exists for one
stated reason: "Every type that reaches a checkpoint must be on the allowlist,
or upgrading LangGraph would make existing conversations unresumable." A read
path that ignores the allowlist means the guarantee is only true of the write
and stream paths. On the LangGraph release that turns the warning into a
refusal, every feature that reads a thread's state breaks: the debugger's gate
detection, the eval runner's verdict read, and any future resume-inspection.
`CombineOp` and `PhaseDisposition` are additionally not on the allowlist at all,
so they break on both paths.

**Why it happens.** Not yet established. The two candidates are that
`AsyncPostgresSaver` decodes some values with its own `jsonplus_serde` rather
than the `serde` passed to `from_conn_string`, and that `aget_state` materialises
channels that `astream` never decodes. Read `AsyncPostgresSaver.aget_tuple` and
`Pregel.aget_state` in `.venv` before choosing.

**Fix.** Establish which serializer decodes which values, then either pass the
allowlisted serde into the path that is missing it, or stop relying on
`with_msgpack_allowlist` and register the types where LangGraph actually reads
them. Add `CombineOp` and `PhaseDisposition` to
`PATHFINDER_CHECKPOINT_TYPES` regardless - they reach a checkpoint and are not
declared. Then assert the absence of the warning: a test that reads a thread's
state under `warnings.catch_warnings(action="error")` fails today and passes
after.

**What you'd get.** A state read that prints nothing, and a LangGraph upgrade
that does not silently remove the ability to inspect a thread.
