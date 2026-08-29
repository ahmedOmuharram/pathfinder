---
type: Backlog Item
title: A fork's copied log rows keep the parent's task_id, so deleting or reverting the parent silently deletes chunks from the fork's append-only log
description: _copy_conversation_events copies task_id verbatim, and conversation_events.task_id is a CASCADE foreign key to background_tasks. Measured, deleting the parent's background_tasks row dropped the fork's event count from 5 to 4. A parent revert deletes its background_tasks rows, and a parent delete cascades them, so either operation on the parent erases rows from a log the fork's clients treat as the source of truth.
tags: [investigation, branching, revert, durable-tasks, persistence, thread-surgery-audit]
generated: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
status: stable
---

# Investigation (thread-surgery audit, 2026-08-28, throwaway rows on the dev stack)

**What I did.** Created a throwaway conversation with 4 chat chunks plus 1
`data-task-progress` row tagged with a `background_tasks` row `869d7668`, forked it,
counted the fork's `conversation_events`, then deleted the parent's task row and
counted again.

**What I got.** Fork event count 5 before the delete, 4 after. The fork's copy of
the task-tagged row was removed by the database, not by any code path that knows
the fork exists.

**Why that is wrong.** PROTOCOL.md section 1: the log is the source of truth and a
client MUST be able to rebuild the conversation from it alone. A fork's log losing
rows because someone reverted or deleted the parent conversation breaks that
rebuild, silently, with no writer anywhere in the stack.

**Why it happens.** `services/conversations/fork.py:71-72` copies `task_id` (and
`turn_id`) verbatim into the new rows, and
`assistant_core/persistence/models.py:197-202` declares
`conversation_events.task_id` as `ForeignKey("background_tasks.id",
ondelete="CASCADE")`. The parent's revert deletes its `background_tasks` rows
(`services/conversations/revert.py:125-132`) and a parent delete cascades them via
the conversation FK; both take the fork's copies with them.

**Fix.** Fork must not couple the child's log lifetime to the parent's rows: either
null `task_id` on copy (the tagged rows are the deprecated per-task dialect; the
thread-visible lifecycle rows carry no task_id), or copy the referenced
`background_tasks` rows too. Decide `turn_id` alongside (it names the parent's turn
message ids, which the fork's messages table does not hold).

**What you would get.** A fork whose log is immutable under any operation on its
parent, measured by an unchanged event count after parent revert and delete.
