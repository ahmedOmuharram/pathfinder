---
type: Backlog Item
title: A fork of a site_help thread comes back as a pathfinder thread, so its next turn runs the wrong graph over the copied checkpoints
description: fork_conversation builds the new Conversation without assistant_id (or application_id), so the column defaults apply. A branch of a site_help conversation measured assistant_id "pathfinder"; its next turn resolves the PathFinder spec, runs the Lead graph over single-agent checkpoints, and the site_help identity gate never runs.
tags: [investigation, branching, assistants, persistence, thread-surgery-audit]
generated: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
status: stable
---

# Investigation (thread-surgery audit, 2026-08-28, throwaway rows on the dev stack)

**What I did.** Created a throwaway conversation `e4305c57` with
`assistant_id="site_help"`, one user and one assistant message, then called
`fork_conversation` anchored on the assistant message and read the fork row back.

**What I got.** Fork `78db3553` with `assistant_id="pathfinder"` while the source
holds `"site_help"`. The fork's checkpoints are the source's, copied by
`_copy_checkpoint_state`.

**Why that is wrong.** `conversations.assistant_id` is documented on the column as
"Set when the thread is created and never changed, so replaying it always runs the
same architecture" (`assistant_core/persistence/models.py:112-118`), and the
dispatcher 409s a body that names another assistant for an existing thread. A fork
silently does what the dispatcher refuses: the branch's next turn resolves the
default spec, runs the two-node Lead graph against checkpoints written by
`single_agent_graph` (whose `TurnState` has no `domain` channel), and skips the
source assistant's identity gate and epilogue.

**Why it happens.** `services/conversations/fork.py:360-367` constructs the fork
`Conversation` with only `id, user_id, site_id, name, parent_conversation_id,
parent_message_id`; `assistant_id` and `application_id` fall to their column
defaults (`DEFAULT_ASSISTANT_ID = "pathfinder"`, the caller's application).

**Fix.** Copy `assistant_id` (and decide `application_id` explicitly) from the
source row in the fork constructor, and pin it with an integration test that forks
a non-default-assistant conversation.

**What you would get.** A branch of a site_help thread stays a site_help thread:
same spec, same graph, same gate.
