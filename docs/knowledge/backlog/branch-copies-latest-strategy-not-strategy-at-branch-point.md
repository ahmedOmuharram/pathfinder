---
type: Backlog Item
title: "Branch to a new chat from here" copies the conversation's latest strategy, not the strategy as it stood at the branched message
description: Branching from the turn-2 answer (a 3-step strategy, root 15) produced a new conversation whose transcript ends at turn 2 but whose strategy is the 4-step one built two turns later (with the P. vivax ortholog transform, root 16), on a fresh WDK strategy id.
tags: [investigation, ui-run, branching, strategy-revision, persistence]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB)

**What I did.** In conversation `4f69357c` (four turns; turn 2 built 3 steps / 15, turn 4
appended a P. vivax ortholog transform / 16), clicked "Branch to a new chat from here" on
the turn-2 assistant message.

**What I got.** New conversation `6bda393a-df89-414c-8f3f-413affd9b20b` with
`parentConversationId 4f69357c`, `parentMessageId f9b7168c...`, `wdkStrategyId 330534153`
(new), `strategyRevision a94b2a277ef8360e` (the parent's *latest* revision), and four steps
including `GenesByOrthologs` (WDK ids `440117043..063`, root 16). Its transcript shows
turns 1-2 only; the Strategy panel shows the 4-step tree with the transform on top.

**Why that is wrong.** The branch's chat says "3 steps, 15 genes" and its strategy is
something else. Any question asked in the branch is answered against a graph the branch's
own history never built. The point of branching from a message is to fork the state at that
message.

**Why it happens.** The branch endpoint copies the conversation's current strategy row
rather than the revision that was current at `parentMessageId`; the strategy revision
recorded on each message (`data-strategy-revision`) is not used to reconstruct the earlier
graph.

**Mechanism sharpened (thread-surgery audit, 2026-08-28).** The two halves of the
fork disagree with each other, not just with the transcript.
`_copy_checkpoint_state` (`services/conversations/fork.py:129-198`) copies only
checkpoints whose `ts` precedes the message after the anchor, so the fork's latest
checkpoint carries `operational_spec`/`spec_before_turn` as they stood at the
branch point, while `fork.py:346-354` copies the latest
`conversation_strategies` AST and duplicates the latest WDK strategy. The fork's
next turn therefore starts with a checkpointed spec describing one tree and a
live strategy describing another; the pre-turn staleness read papers over it from
the live side. Revert has the mirror defect, filed as
[revert-leaves-the-strategy-at-post-turn-state](revert-leaves-the-strategy-at-post-turn-state.md).

**Fix (to decide).** Store the full strategy snapshot per revision (or per build), and have
branch (and edit/revert) materialise the revision referenced by the branched message into
the new conversation and into a new WDK strategy. If a revision cannot be reconstructed,
say so in the branch header instead of copying the latest.

**What you would get.** The branch opens with the 3-step strategy, root 15, and a WDK
strategy that matches its transcript.
