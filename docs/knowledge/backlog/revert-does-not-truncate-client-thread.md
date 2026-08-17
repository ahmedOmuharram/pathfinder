---
type: Backlog Item
title: After a successful Revert the client keeps rendering the reverted turns and appends the edited message below them until the page is reloaded
description: POST /revert-to-message returned 204 and the server deleted the turn, but the assistant-ui thread still showed the deleted user message and its answer, with the edited message and its new answer appended underneath. Only a reload showed the truncated thread.
tags: [investigation, ui-run, revert, chat, client-state]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB, conversation 4f69357c)

**What I did.** Edited the fourth user message ("Now add a step at the end that
transforms the result into P. vivax P01 orthologs.") to a different instruction, Save,
chose "Revert this chat", Revert.

**What I got.** `POST /api/v1/conversations/4f69357c.../revert-to-message -> 204`. The
thread still showed the original fourth message and its full answer ("... returns an
estimated 16 P. vivax P01 orthologs at the root."), followed by the edited message as a
new fifth turn and its answer. After the turn finished and I reloaded, the thread showed
turns 1-3 and the edited message only, which is the server's state.

**Why that is wrong.** For the length of that turn the user reads two contradictory
histories on one screen (an answer that says "4 steps, 16 orthologs" above an answer that
says "5 steps, 46 genes"), and the message list they see is not the one the model was
given.

**Why it happens.** The revert flow calls the endpoint and then sends the edited message,
but does not drop the reverted messages from the client-side thread (assistant-ui message
repository / useChat messages) before appending.

**Fix (to decide).** After a 204 from revert, truncate the client thread at the target
message (or refetch the snapshot) before sending the edit; the branch path already opens
a fresh conversation and does not have this problem.

**What you would get.** The thread visibly shortens at the moment Revert is confirmed,
then the edited message streams as the last turn.
