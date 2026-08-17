---
type: Backlog Item
title: An approval-required tool called inside a sub-agent never reaches the user, so the turn either raises TypeError or reports that nothing happened
description: optimize_search_parameters, delete_step and clear_strategy carry requires_approval=True on the verification and execution sub-agent toolsets, but a sub-agent run is not streamed through the VercelAI adapter and its DeferredToolRequests output is dropped by an isinstance filter. A scripted run emits no tool-approval-request chunk, ends verify_strategy in TypeError, and ends recover_failed_steps in an empty RecoveryDelta. Only the Lead's consult_user reaches the approval controls.
tags: [investigation, agents, sub-agents, approvals, safety, streaming]
generated: { by: claude-code/opus-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (scripted reproduction, 2026-08-17)

**What I did.** Drove three production entry points with a scripted pydantic-ai
`FunctionModel` (no network, no Postgres, `PATHFINDER_CHAT_PROVIDER=mock` with the
mock swapped for the script). Each scripted model calls one approval-required tool
on its first model turn, then emits the agent's typed output on the second.

- `sub_agent_dispatch.verify_strategy(reason="optimize the RNA-Seq fold change
  against the controls")` with the verification sub-agent calling
  `optimize_search_parameters(target={search_name "GenesByRNASeqEvidence",
  parameter_space [min_fold_change 1.5-4.0]}, controls={positive
  ["PF3D7_1133400"], negative ["PF3D7_0930300"]}, settings={budget 8})`.
- `sub_agent_dispatch.recover_failed_steps(reason="drop the step that failed to
  push")` with the execution sub-agent calling `delete_step(step_id="s2")`.
- `lead_node._drive_lead_stream` with the Lead calling `consult_user(questions=[
  {id "q1", prompt "Fold-change threshold?"}])`, as the contrast.

The langgraph stream writer was replaced with a collector, so every chunk the
production code emits was captured.

**What I got.** The two sub-agent paths emit no approval chunk at all:

```
=== A. verification sub-agent, optimize_search_parameters ===
  approval chunk emitted     : NO
  sub-agent step chunks      : ['optimize_search_parameters:started']
  distinct chunk types       : ['data-sub-agent-step', 'data-turn-status']
  returned output type       : NoneType
  exception                  : TypeError: Verification sub-agent did not return a
                               VerificationDelta.

=== B. execution sub-agent, delete_step ===
  approval chunk emitted     : NO
  sub-agent step chunks      : ['delete_step:started']
  returned output type       : RecoveryDelta
  returned output value      : RecoveryDelta(actions_taken=[], follow_up_needed=False)
  exception                  : none

=== C. Lead agent, consult_user (contrast) ===
  approval chunk emitted     : YES
  approval chunk             : {"type": "tool-approval-request",
                                "approvalId": "call_consult_user",
                                "toolCallId": "call_consult_user"}
  returned output type       : PendingApproval
  returned output value      : PendingApproval(phase='lead',
                               tool_call_id='call_consult_user',
                               tool_name='consult_user',
                               prior_messages_json=6217 chars)
  exception                  : none
```

The same verification run inspected one layer lower shows what is thrown away:

```
=== D. what _stream_sub_agent drops ===
  sub-agent run output type  : DeferredToolRequests
  approvals awaiting a user  : [('optimize_search_parameters',
                                'call_optimize_search_parameters')]
  isinstance(output, VerificationDelta): False
```

**Why that is wrong.** Three of the four approval-required tools are unreachable.
A user can never approve or deny `optimize_search_parameters` (a ~15 minute worker
sweep), `delete_step`, or `clear_strategy`, so the guard on the two destructive
strategy tools protects nothing and the expensive one can never run. The
verification request ends the turn in a `TypeError` with no user-facing answer;
the recovery request is worse, because it returns cleanly with an empty delta and
the Lead reads "the sub-agent did nothing" when the sub-agent in fact stopped at
an unanswered approval. The generic approval card
(`features/conversation/content/parts/ToolApprovalControls.tsx`) renders for any
non-consult tool, so it is already built and can only ever fire for
`consult_user`.

**Why it happens.** `ai/lead/sub_agent_tools.py:_stream_sub_agent` calls
`agent.run_stream_events` with no `deferred_tool_results` (390-395) and keeps the
run output only when `isinstance(agent_output, expected_output_type)` (397-400),
so a `DeferredToolRequests` output is discarded, while `_forward_inner_event`
(237-310) forwards only `FunctionToolCallEvent`, `FunctionToolResultEvent` and
`PartEndEvent` into `data-sub-agent-step` chunks and has no branch that can emit a
`ToolApprovalRequestChunk`; only the Lead's run passes through
`PhaseStreamEmitter`, whose `VercelAIEventStream` is the single place that turns a
`DeferredToolRequests` output into that chunk.

**Fix (to decide).** Three shapes, in decreasing cost:

- Forward the sub-agent's approval to the client and resume the sub-agent. The
  sub-agent's message history must be checkpointed on `PendingApproval` (its
  `phase` field already allows `verification` and `build`), and the resume must
  re-enter the right sub-agent with `DeferredToolResults` rather than re-entering
  the Lead.
- Return a typed "needs approval" delta to the Lead. The sub-agent stops, the Lead
  asks through `consult_user`, and re-dispatches with the answer as a constraint.
  Cheaper, but the tool call is re-decided by the model rather than resumed.
- Enforce approval only at Lead level and drop `requires_approval` from the
  sub-agent tools. Honest about today's capability, but it moves the destructive
  guard away from the call site.

Whichever is chosen, `verify_strategy` must stop reporting an unanswered approval
as a `TypeError`, and `recover_failed_steps` must stop reporting it as an empty
`RecoveryDelta`.

**What you would get.** The verification request streams a
`tool-approval-request` for `optimize_search_parameters`, the approval card
appears with the target and controls shown, and the answer either starts the
sweep or returns a denial the sub-agent can act on; the same for `delete_step`
and `clear_strategy`. No turn ends in `TypeError`, and no turn reports an empty
recovery when the real state is "waiting on the user".
