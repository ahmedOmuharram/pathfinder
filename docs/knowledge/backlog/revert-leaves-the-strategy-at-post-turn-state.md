---
type: Backlog Item
title: Revert truncates the transcript and the checkpoints but not the strategy, so the surviving thread describes a strategy the panel no longer shows
description: revert_conversation_to_message deletes messages, events, notes, background_tasks and checkpoints at or after the target, and touches neither conversation_strategies nor the WDK strategy. Measured, a marker AST with 4 steps survived a revert that deleted the turn that built it. The next turn's live-state read then quotes a strategy the visible transcript never built, the revert twin of the filed branch-copies-latest bug.
tags: [investigation, revert, strategy-revision, persistence, thread-surgery-audit]
generated: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
status: stable
---

# Investigation (thread-surgery audit, 2026-08-28, throwaway rows on the dev stack)

**What I did.** Created a throwaway conversation `e4305c57` with a user message, an
assistant message, their chunks, and a `ConversationStrategy` row holding
`{"marker": "POST-TURN-AST", "steps": [1, 2, 3, 4]}`; then called
`revert_conversation_to_message` targeting the user message.

**What I got.** The revert deleted 1 message and 4 events and logged
`deleted_checkpoints`/`deleted_tasks` counts, and the strategy row read back intact:
`{"steps": [1, 2, 3, 4], "marker": "POST-TURN-AST"}`, `step_count` 4.

**Why that is wrong.** After reverting past the turn that appended a step, the user
reads a transcript that ends before the build while the Strategy panel, the next
turn's `get_live_strategy_state`, and every count the Lead quotes describe the
post-build graph. The model is grounded in state the visible history disavows,
which is the same contradiction the filed
[branch-copies-latest](branch-copies-latest-strategy-not-strategy-at-branch-point.md)
item measured for fork, on the other side of the same missing revision store.

**Why it happens.** `services/conversations/revert.py:100-164` deletes six things
(messages, notes, events, background_tasks, checkpoint_writes, checkpoints) and
never reads `conversation_strategies` or the WDK strategy; no strategy revision
snapshot exists that a revert could materialize.

**Fix.** The same decision the branch item defers to: store the strategy snapshot
per revision and have revert (with branch and edit) materialize the revision
referenced by the target message, or state loudly in the thread that the strategy
did not follow the revert. Deleting the checkpointed spec while keeping the live
AST is the worst of both.

**What you would get.** After a revert, the panel, the live-state read, and the
transcript agree on one strategy.
