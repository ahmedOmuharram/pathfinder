---
type: Decision
title: The tools that change a strategy are hidden until the turn is classified as one that asks for a change
description: A pydantic-ai `PrepareTools` capability drops `frame_problem`, `build_strategy`, `edit_strategy`, `recover_failed_steps`, `verify_strategy` and the four writing EDA tools from the Lead's tool list unless this turn's `UserIntent` is one of six building classifications. The instruction-only alternative was rejected because two measured runs already ignored it.
tags: [agents, lead, intent, cost]
generated: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
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

**Gating before any classification.** The gate reads the intent the turn
carries, which on a continuation is the one the previous turn recorded. Hiding
the tools until the model classifies again would stop every turn on which a
model, or the deterministic test script, does not re-classify, and a Lead that
cannot see `build_strategy` cannot ask for it back except through
`classify_user_intent`. The recorded intent is the safe default; the
deterministic provider now classifies once per turn so its arcs state their own
intent.
