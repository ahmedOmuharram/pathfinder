---
type: Decision
title: One id names one message in the log
description: The dispatcher appends a user envelope only when the log has no envelope for that id, and the snapshot reducer keeps the first message an id names; minting a server-side id, branching on `trigger`, a unique index and a repair of existing rows were all rejected.
tags: [chat, persistence, protocol, regenerate, assistant-ui]
generated: { by: claude-code/opus-5, at: 2026-08-25T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-25T00:00:00Z }
status: stable
---

# What was decided

A client rebuilds its thread from the log, so an id in the log names exactly one
message. Two places hold that invariant.

The runtime writes it once. `dispatch` calls
`assistant_core.conversation.event_writer.append_user_message_once`, which reads
the log for a `user-message` envelope with that id and appends nothing when it
finds one. A regenerate sends the thread back ending at the same user message,
and so does a client that lost its response and retried; neither adds a second
envelope.

The client reads it once. `reduceSnapshot` keeps the first message an id names
and drops a later one, so a log written before the runtime held the invariant
still builds a thread.

# Why not mint a fresh id for the replay

Section 12.2 of `PROTOCOL.md` says the last message's `id` becomes the id of the
log row the runtime writes for it. A server-minted id puts the client's copy of
the thread and the log's copy under different ids, which is the split that makes
per-message actions address a message the conversation does not hold.

# Why not branch on `trigger`

Section 12.3 says `trigger` is recorded, not branched on: what the turn does is
decided by the last entry in `messages`. The id is the fact; the trigger is the
client's account of why it sent it. Keying on the id covers a replay that names
no trigger at all.

# Why not a unique index, and no repair of existing rows

A unique index on `(conversation_id, chunk -> message -> id)` cannot be created
over a log that already repeats an id, and a repair rewrites an append-only log
that is the source of truth for what was said. The reducer's rule makes an
existing repeat non-fatal instead, so no history is edited. What remains is a
window: two identical ids posted at the same instant can both read an empty log
and both write. The thread still builds, because the reducer drops the second.

# What this does not do

It does not make the two answers siblings of one question. A regenerate leaves
both attempts on the thread, in the order the log holds them, because the log
records what happened.
