---
type: Backlog Item
title: A resumed approval turn emits tool-input-available without tool-input-start, so the producer and PROTOCOL 6.2 disagree on the letter
description: Measured on a mock consult_user arc (2026-08-24, devtools run fable-a/turn2) - the resumed turn re-enters the parked toolCallId with tool-input-available then tool-output-available, and no tool-input-start precedes them. pydantic-ai's resume emits its own input-available, which marks the id as started, so PhaseStreamEmitter._synthesize_missing_start (assistant_core/conversation/vercel_adapter.py:180-207) never backfills the start. The strict client tolerates it (reduceTool.ts:138-139 opens a track on available), so nothing breaks for a user, but PROTOCOL section 6.2 describes a start-first sequence. Fix is one decision - synthesize the start unconditionally on resume, or relax 6.2's wording to admit the resume shape - plus a conformance case pinning whichever is chosen.
tags: [protocol, approvals, sse, runtime]
generated: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-25T00:00:00Z }
status: stable
---

**What I did.** Drove a two-turn consult_user approval arc through the
devtools debugger (mock provider) on the rebuilt dev stack and diffed the
chunk logs against PROTOCOL section 6.2.

**What I got.** Turn 1 conforms exactly (tool-input-start, then
tool-input-available, then tool-approval-request, finish, done). Turn 2
re-enters the same toolCallId with tool-input-available then
tool-output-available and never emits tool-input-start.

**Why that is wrong.** The document says a consumer can be implemented from
the page alone; a consumer that trusts 6.2's start-first sequence on the
resume half builds a reader the reference producer contradicts.

**Why it happens.** pydantic-ai's resume path emits its own input-available
for the parked call, which marks the id started, so the adapter's
_synthesize_missing_start backfill never fires
(assistant_core/conversation/vercel_adapter.py:180-207).

**Fix.** Either synthesize the start unconditionally on resume, or relax
6.2's resume wording; then pin the choice with a conformance case on both
sides of the protocol.

**What you would get.** A resume sequence the document and the producer
state identically, and a client buildable from the page alone.

**Measured again over a network tool source.** A site-help turn whose
approval-gated tool is served over MCP reads the same way: turn 1 is
tool-input-start, tool-input-available, tool-approval-request; turn 2 is
tool-input-available, tool-output-available. The shape is the runtime's, not
one tool kind's. Pinned as it stands by
`tests/integration/http/test_site_help_tool_source.py::test_the_answered_card_runs_the_source_s_tool_on_the_next_request`,
which fails when the start is restored.
