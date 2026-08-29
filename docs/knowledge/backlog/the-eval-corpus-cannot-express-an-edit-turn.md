---
type: Backlog Item
title: An eval case is one prompt on a fresh thread, so no case can pin an edit-turn regression
description: "`run_one_case` mints a new conversation id and drives `case.prompt` once. An edit turn is a second message against a strategy that already exists, so the two edit defects the corpus should pin - a dropped criterion reported as preserved, and a rebuild that changes every WDK step id - have no case shape to be written in."
tags: [evals, verification-gates, strategy]
generated: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
status: stable
---

# What I did

Went to promote a case from each of the two closed edit items, per
`conventions/verification-gates.md`: "a case written from a failure already in
the backlog qualifies once it is shown to fail on the code that had the bug and
pass on the code that fixed it." Read the case shape and the driver.

# What I got

`apps/api/src/pathfinder/evals/case.py` declares `EvalCase` with one `prompt`
and an `ExpectedOutcome` of `builds_strategy`, `structure`, `record_type`,
`step_count`, `verified`, `reply_mentions`, `reply_omits`.
`apps/api/src/pathfinder/devtools/eval_runner.py:87-104`:

```
async def run_one_case(case, *, run_root, mock=True) -> ObservedOutcome:
    """Drive one case on a fresh thread and read what it left behind."""
    conversation_id = uuid4()
```

There is no field for a starting strategy and no second prompt.

# Why that's wrong

The two defects the edit work closed are both second-turn defects. Turn 1 builds
three criteria; turn 2 says "change X, keep the rest" and comes back with two.
Turn 1 builds three steps; turn 2 says "add a transform at the end" and every
WDK step id changes. A single-prompt case cannot reach either state, so the
gate that is supposed to hold the fix in place does not exist, and the next
change to `ai/lead/` can undo it with a green corpus.

The unit and integration suites do cover the mechanism
(`tests/unit/domain/strategy/test_spec_to_operations.py`,
`tests/integration/services/strategies/test_edit_preserves_step_ids.py`,
`tests/integration/ai/test_organism_swap_turn.py`). Those hold the seam. The
corpus is what would hold the *model's routing* under a real provider, and it
cannot.

# Why it happens

The corpus was built for "does the assistant do the right thing with one
underspecified request". Nothing in it needed a prior turn until now.

# Fix

Give `EvalCase` a `turns: list[str]` (one entry is today's single prompt, so no
case changes) and drive them in order on one conversation id in `run_one_case`.
Add `expected.preservedStepIds: bool` or an `expected.stepIdsUnchanged` flag,
observed from `conversation_strategies.strategy_ast`'s `wdkStepIds` before and
after the last turn. Then write the two cases:
`edit-keeps-the-criteria-it-was-told-to-keep` and
`edit-does-not-mint-new-wdk-step-ids`, and show each failing on the pre-fix code.

# What you'd get

`uv run python -m pathfinder.devtools.evals run` reporting a verdict for a
two-turn edit case, and a corpus that would have caught both filed defects.
