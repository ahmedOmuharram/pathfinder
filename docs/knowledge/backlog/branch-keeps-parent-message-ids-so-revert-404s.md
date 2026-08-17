---
type: Backlog Item
title: A branched conversation replays the parent's message ids, so Revert (and any per-message action) in the branch 404s and the dialog gives no feedback
description: fork.py inserts new Message rows with fresh uuids but copies the event chunks with the parent's message ids untouched. The branch UI builds its thread from those chunks, so "Edit -> Revert this chat" posts the parent's message id and gets 404 "Target message not found"; the dialog stays open with no error.
tags: [investigation, ui-run, branching, revert, persistence, ux]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB)

**What I did.** In branch `6bda393a` (forked from `4f69357c` at its second user message),
clicked Edit on that user message, changed the text, Save, chose "Revert this chat" in
the "Edit earlier message" dialog. Clicked Revert twice (mouse and programmatic).

**What I got.** `POST /api/v1/conversations/6bda393a.../revert-to-message` -> 404
`{"title":"Target message not found","code":"NOT_FOUND"}` (twice). The dialog stayed
open, no toast, no message. Console: nothing new. The server branch that produces this
text is `services/conversations/revert.py` "target message not in conversation" (the
message row exists but belongs to another conversation).

**Why that is wrong.** Revert is advertised in the dialog and does nothing; the user
cannot tell whether it is slow, forbidden, or broken. Any per-message action addressed by
id in a branch (revert, regenerate, branch-again, feedback) is exposed to the same mismatch.

**Why it happens.** `services/conversations/fork.py` creates the branch's `Message` rows
with `id=uuid4()` but copies the event chunks (`user-message`, `start`, ...) with the
parent's `messageId` values; only scratchpad note ids are rewritten
(`_rewrite_scratchpad_ids_in_chunk`). The UI's thread is built from the chunks, so its
message ids are the parent's.

**Fix (to decide).** Fork must keep one id space: either reuse the parent's message ids
for the copied `Message` rows (they are unique per conversation, so `(conversation_id, id)`
stays unique) or rewrite `messageId`/`message.id` in every copied chunk through the same
id map used for notes. And the edit dialog must surface a failed revert/branch as an error
and close or re-enable.

**What you would get.** Revert in a branch deletes from the chosen message onward; a
failure shows "Could not revert: ..." in the dialog.
