---
type: Decision
title: A thread accumulates every requirement its user states, and a clarification adds to that list instead of replacing it
description: `StrategyDomainState.requirements` collects each turn's `UserIntent.explicit_constraints`, deduped on kind AND value so two free-form requirements never collapse. The ledger renders the whole list and a fresh spec's goal is seeded from the original request plus the clarification, so a clarification turn frames from both.
tags: [agents, lead, intent, frame, context]
generated: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-30T00:00:00Z }
status: stable
---

# The decision

`UserIntent.explicit_constraints` is per message. It was also the only thing
the ledger's constraint section and a fresh FRAME pass ever saw, so a
clarification turn framed from the answer alone.

- `StrategyDomainState.requirements` is the thread's list, oldest first.
  `classify_user_intent` appends this turn's constraints through
  `record_intent`, deduped on `(kind, requested_value)`. It is cleared only by
  a `new_strategy` classification on a thread that holds no strategy.
- `StrategyDomainState.original_request` is the text of the first turn whose
  classification states a request of its own (`new_strategy`,
  `extend_strategy`, `edit_strategy`). A `clarification_response` never writes
  it.
- `ai/lead/derive.py` merges the accumulated list into the constraint section,
  and `InvestigationLedger.render_summary` prints one line per stated
  requirement, so the Lead can see a value it already has and not ask again.
- `ai/lead/dispatch_context.py::framing_goal` seeds a missing spec's goal with
  the original request, then the clarification, so FRAME reads both.

# What was rejected

**Deduping the accumulation by dimension only.** `merge_constraints` collapses
by `ConstraintKind`, which is right for "the latest organism wins" and wrong
for the free-form kind: a motif literal and a distance rule are both
`ConstraintKind.OTHER`, and the second would silently delete the first - the
exact loss the cataloged item reports. `derive.py` therefore keeps
`merge_constraints` for the per-dimension override of the spec's assumed
constraints, then re-adds every stated requirement the collapse dropped.

**Replacing the requirement list on every turn.** That is the behaviour being
replaced. A clarification states less than the request it answers, so a
replacement loses the request.
