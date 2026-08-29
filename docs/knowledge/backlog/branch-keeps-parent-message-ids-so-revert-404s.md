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

**Mechanism correction (thread-surgery audit, 2026-08-28).** The "reuse the
parent's message ids" option is not available: `messages.id` is the primary key
alone, not `(conversation_id, id)` (`assistant_core/persistence/models.py:162`),
so a copied row under the parent's id collides. Worse, the id space is squatted
forever: `MessagesRepository.insert_message` is
`on_conflict_do_nothing(index_elements=[Message.id])`
(`assistant_core/persistence/repositories/message.py:35`), so measured on the dev
stack, inserting a message row into conversation B with an id conversation A holds
silently persists nothing (the id's only row stays A's). A regenerate or
edit-resend in a branch, which posts a copied chunk id, therefore records no
Message row in the branch at all, and every per-message action on that turn stays
broken afterwards. The workable direction is rewriting `messageId`/`message.id`
in every copied chunk through an id map (as notes already do), or widening the
primary key, a schema decision.

**Fix (to decide).** Fork must keep one id space: rewrite `messageId`/`message.id`
in every copied chunk through the same id map used for notes (or make the message
PK per-conversation). And the edit dialog must surface a failed revert/branch as
an error and close or re-enable.

**What you would get.** Revert in a branch deletes from the chosen message onward; a
failure shows "Could not revert: ..." in the dialog.
