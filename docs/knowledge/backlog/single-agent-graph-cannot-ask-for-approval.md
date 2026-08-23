---
type: Backlog Item
title: A one-agent assistant that marks a tool approval-required gets an error, not an approval card
description: single_agent_graph runs its agent with output_type str and never resolves a deferred call, so requires_approval=True raises a UserError that reaches the user as a red error chunk; pending_approval and approval_responses are declared on TurnState and written by nothing.
tags: [assistant-core, approvals, ws-v, runtime]
generated: { by: claude-code/opus-5, at: 2026-08-22T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-22T00:00:00Z }
status: stable
---

# What I did

Built an assistant from runtime code alone: `single_agent_graph` over bare
`TurnState`, a scripted model, and one tool declared
`Tool(wipe_everything, requires_approval=True)`. Drove one turn whose prompt
makes the script call that tool once
(`packages/assistant-core/tests/integration/conversation/test_approvals.py`).

# What I got

The turn's chunks, in order, from the durable log:

```
tool-input-start      {"toolCallId": "call_wipe", "toolName": "wipe_everything"}
tool-input-available  {"toolCallId": "call_wipe", "input": {"target": "everything"}}
tool-output-error     {"toolCallId": "call_wipe", "errorText": "Tool execution was interrupted by an error."}
error                 {"errorText": "A deferred tool call was present, but `DeferredToolRequests` is not among output types. ..."}
finish                {"finishReason": "stop"}
done
```

No `tool-approval-request` chunk. The reduced message carries the call in
state `output-error` with no `output`. The thread's checkpoint has no
`pending_approval` channel at all, and `approval_responses` is `{}`.

# Why that's wrong

The user asked for a destructive action, the assistant asked for confirmation,
and the confirmation card never appeared. Instead the conversation shows a red
error naming a pydantic-ai output type, which means nothing to a researcher.
The tool did not run, so nothing is corrupted, but the assistant is now unable
to complete a request it was correctly cautious about, and the only way past it
is to remove the safety flag.

The runtime declares the whole approval vocabulary and none of it is reachable
from the graph it ships: `TurnStart.approval_responses` and
`TurnState.pending_approval` exist, `ToolApprovalRequestChunk` and
`ToolOutputDeniedChunk` travel the wire, the chunk reducer moves a part to
`approval-requested`, and `PhaseStreamEmitter` backfills the deferred call's
start chunk on resume. Only the turn graph is missing.

# Why it happens

`assistant_core/graph/single_agent.py::single_agent_graph` types its agent as
`Agent[DepsT, str]` and calls `run_stream_events` with no
`DeferredToolRequests` in the output union, no `deferred_tool_results` on the
resume path and no `message_history`. pydantic-ai's `_tool_execution` raises
`UserError` when a deferred call has nowhere to go, and
`PinnedVercelAIEventStream.on_error` converts that into an `ErrorChunk`.

PathFinder's own Lead does implement the cycle, in
`apps/api/src/pathfinder/ai/graph/lead_node.py` and `_lead_turn.py`, so the
capability exists in the repository but not in the runtime. The second
assistant (`assistants/site_help`) is built on `single_agent_graph` and
therefore cannot ask for approval today.

# Fix

Give the single-agent graph the deferred-tool cycle the Lead already has, in
the runtime rather than a second copy in the product:

1. Widen the graph's agent to `output_type=[str, DeferredToolRequests]`.
2. On a `DeferredToolRequests` output, write `PendingApproval` onto the state
   (tool call id, name, args, and the run's messages serialized) and let the
   emitter's `ToolApprovalRequestChunk` reach the client.
3. On a turn with `is_resume=True`, rebuild `DeferredToolResults` from
   `state.approval_responses`, restore `prior_messages_json` as
   `message_history`, and continue the run.
4. Then lift the Lead onto the same helper, so the cycle is stated once.

# What you'd get

The same turn ends at `tool-approval-request` for `call_wipe`, with the turn's
`finish` and `done` after it. The next turn, carrying the user's answer,
produces `tool-output-available` when approved and `tool-output-denied` when
refused, and the thread's `pending_approval` returns to unset.
