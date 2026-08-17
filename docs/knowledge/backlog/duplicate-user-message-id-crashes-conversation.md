---
type: Backlog Item
title: A regenerated turn replays the user message with its original id, and assistant-ui then crashes the whole chat view for that conversation forever
description: The persisted event stream of one conversation contains two user-message chunks with the same message id (the second from a regenerate after a build error). On load, assistant-ui's MessageRepository throws "A message with the same id already exists in the parent tree", the ChatViewBody error boundary shows "Application error", Retry does not help, and the conversation cannot be opened again.
tags: [investigation, ui-run, chat, persistence, regenerate, assistant-ui]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB)

**What I did.** From the conversation sidebar, opened "P. falciparum Kinase Drug Targets"
(conversation `57f3fcf1-1105-406d-a3fb-5d54dcf19f45`, 15 steps, dated Aug 15). Also
reloaded the URL directly.

**What I got.** Full-page "Application error: MessageRepository(performOp/link): A message
with the same id already exists in the parent tree. This error occurs if the same message
id is found multiple times. This is likely an internal bug in assistant-ui." Console also
shows `TypeError: Cannot read properties of undefined (reading 'state')` from
`ai/dist/index.mjs`. Retry re-throws.
`GET /api/v1/conversations/57f3fcf1.../events/snapshot` returns 1,624 chunks; the
`user-message` chunk with `message.id = 43f33eec-e6d5-44bb-b6d3-b367e7dfc888` appears at
index 0 and again at index 806, followed each time by a different assistant `start`
(`5e47a007...` then `1d25d96f...`). Between them, index 796 is
`{"type":"error","errorText":"combine node needs an operator and at least two inputs"}`.

**Why that is wrong.** One conversation with a 15-step strategy is unreachable in the UI;
there is no message about which conversation is broken or why, and no way to recover from
the chat surface. Any conversation that was ever regenerated after an error is at risk.

**Why it happens.** The regenerate path re-emits the original user message into the event
stream under its original id instead of a new one (or instead of omitting it), and the
snapshot replay feeds every `user-message` chunk to assistant-ui as a new node.

**Fix (to decide).** Regenerate must not append a second `user-message` with the same id:
either branch from the existing user node (assistant-ui supports multiple assistant children
per user message) or mint a new id. The snapshot loader should also dedupe on message id so
already-persisted conversations open again. Add a repair for existing rows.

**What you would get.** The conversation opens; the two assistant attempts show as
siblings under the one user message.
