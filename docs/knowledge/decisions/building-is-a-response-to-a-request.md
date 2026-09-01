---
type: Decision
title: The tools that change a strategy are hidden until the turn is classified as one that asks for a change
description: A pydantic-ai `PrepareTools` capability drops `frame_problem`, `build_strategy`, `edit_strategy`, `recover_failed_steps`, `verify_strategy` and the four writing EDA tools from the Lead's tool list unless this turn's `UserIntent` is one of six building classifications. The instruction-only alternative was rejected because two measured runs already ignored it, and a gate that can dead-end is rejected too: a misclassified turn is corrected by re-classifying inside the same run, which unhides the tools on the next step.
tags: [agents, lead, intent, cost]
generated: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-31T00:00:00Z }
status: stable
---

# The decision

Two `IntentClassification` values name a turn that asks for no strategy:
`context_statement` ("I'm investigating virulence factors in Leishmania major")
and `memory_request` ("Please remember for future sessions: ..."). Six name a
turn that does: `new_strategy`, `extend_strategy`, `edit_strategy`,
`clarification_response`, `slot_answer`, `approval`. The set lives in
`ai/lead/intent.py::BUILDING_INTENTS`.

`ai/lead/intent_gate.py::hide_building_tools` is registered on the Lead as
`PrepareTools[LeadDeps]`. On every model step it removes
`BUILDING_TOOLS` - the five dispatch tools plus `open_eda_analysis`,
`set_eda_filters`, `run_eda_compute` and `create_eda_step` - unless
`LeadDeps.intent` names a building classification. `remember` and every
read-only tool stay. The Lead's instructions say that classifying again with
the right value is the only thing that puts a missing tool back.

**A misclassification degrades; it never dead-ends.** `PrepareTools` runs on
every model step and reads `LeadDeps` live, so a classification corrected inside
the same run puts the tools back on the very next step - one wasted step, not a
refused turn. The Lead's rules name that path as the FIRST action when the
message asks it to run, rerun, build, add or create and the building tools are
absent, and they forbid both telling the user that a tool is unavailable this
turn and asking the user to retry the request. `classify_user_intent` states
that such an imperative - a bare "yes, do it" that accepts the assistant's own
offer, and a retry after a failed task, included - is a building
classification and never a `follow_up_question`.
`tests/unit/ai/lead/test_intent_gates_building_tools.py::test_a_corrected_classification_unhides_the_building_tools`
pins the unhiding, and
`tests/unit/ai/lead/test_imperatives_are_building_intents.py` pins the guidance.

`ai/lead/memory_candidates.py` follows the same rule: a turn whose recorded
classification is not a building one contributes no strategy memory, so a
preference request cannot leave a strategy memory summarised by the user's
sentence.

# What was rejected

**An instruction alone.** The cataloged item proposed either a mechanical gate
or one more sentence in the Lead's prompt. Two measured runs on the default
provider already framed, built and verified a strategy for a bare context
sentence and for a preference request, so a rule the model may or may not
follow was not enough. The instruction is still written, but it explains a gate
that holds without it.

**A gate that can dead-end.** A hidden tool the Lead cannot ask back is a
turn the user pays for and gets nothing from: the measured refusal, "the
analysis controls ... are not available in this turn. Please retry this
request.", cost two turns. The gate is kept only because the correction path is
always open and the instructions make it the first move.

**Gating before any classification.** The gate reads the intent the turn
carries, which on a continuation is the one the previous turn recorded. Hiding
the tools until the model classifies again would stop every turn on which a
model, or the deterministic test script, does not re-classify, and a Lead that
cannot see `build_strategy` cannot ask for it back except through
`classify_user_intent`. The recorded intent is the safe default; the
deterministic provider now classifies once per turn so its arcs state their own
intent.
