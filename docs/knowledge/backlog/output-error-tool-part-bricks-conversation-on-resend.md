---
type: Backlog Item
title: One failed tool call (classify_user_intent refusing a 3-way comparison) leaves an output-error part with resultProviderMetadata in the history, and every later send in that conversation is a 422
description: The intent classifier's schema caps differential_sides at 2; a "compare A, B, C" prompt made the model's first call fail validation, which the stream recorded as a tool part in state output-error carrying resultProviderMetadata. pydantic-ai's ToolOutputErrorPart forbids that key, so ChatRequestBody.messages fails to parse on the next submit (consult answer) and on any submit after it. The user sees the raw pydantic error list.
tags: [investigation, ui-run, chat, transport, pydantic-ai, intent, consult]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB, conversation 4f69357c)

**What I did.** Sent "Run an experiment comparing the Su et al. gametocyte filter at
three thresholds (top 20%, top 10%, top 5%) ...". The turn ended in a consult_user
question; I picked "Top 10%", typed a note, and pressed Submit.

**What I got.** `POST /api/v1/chat -> 422 {"title":"Request validation failed", ...
"errors":[{"loc":["body","messages",9,"parts",4,"TextUIPart","type"], "input":
"tool-classify_user_intent"}, ...]}` and the chat rendered the whole `detail` string
("Input should be 'text'; Field required; Input should be 'streaming' or 'done'; Extra
inputs are not permitted; ..." several hundred words). The offending part:
`{"type":"tool-classify_user_intent","state":"output-error","toolCallId":"call_qL0X...",
"rawInput":{...,"differentialSides":["top 20%","top 10%","top 5%"],...},
"errorText":"1 validation error: ... differentialSides: List should have at most 2 items
after validation, not 3 ...","callProviderMetadata":{...},"resultProviderMetadata":{...}}`.
Reproduced in the api container: `UIMessage.model_validate` on that part fails with
`ToolOutputErrorPart.resultProviderMetadata: Extra inputs are not permitted` and passes
once the key is removed.

**Why that is wrong.** The conversation is dead from that point: every submit re-sends
the history and every submit 422s. The failure is a schema nit (a 3-way comparison is a
normal request) surfacing as a wall of validator text.

**Why it happens.** Two layers. `ai/lead/intent.py:UserIntent.differential_sides` has
`max_length=2`, so a three-sided comparison always fails once before the model retries
with two sides. `assistant_core/conversation/_chunk_state.py:_provider_metadata_key` writes
`resultProviderMetadata` on output-available and output-error parts (as the AI SDK v6
client does, `ai/dist/index.mjs`), but pydantic-ai 1.104's
`ui/vercel_ai/request_types.py` defines only `call_provider_metadata` on every tool part
with extra forbidden, so a message containing an output-error part with
`resultProviderMetadata` can never be sent back through `ChatRequestBody`.

**Fix (to decide).** Lift the `max_length=2` (allow 2..N sides, or make it a set of
labels); and make the request boundary tolerant of the SDK's own part shape: either strip
`resultProviderMetadata` before validation (a `@field_validator(mode="before")` on
`ChatRequestBody.messages`) or carry a local `UIMessage` subclass that accepts it. Add a
test that a history with an output-error tool part round-trips. The 422 handler in the
chat UI should show a one-line message, not the validator dump.

**What you would get.** A 3-way comparison classifies on the first call; a conversation
that once had a failed tool call keeps accepting messages.
