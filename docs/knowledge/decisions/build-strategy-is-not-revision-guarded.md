---
type: Decision
title: build_strategy is deliberately not revision-guarded
description: An accepted exposure, recorded so it is not mistaken for an oversight.
tags: [agents, concurrency, r4, accepted-risk]
generated: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
verified: { by: human:ahmedOmuharram, at: 2026-08-09T00:00:00Z }
status: stable
---

# The guard that exists

`apply_operations(base_revision, operations)` treats `strategy_revision` as a **write precondition**. A mismatch raises `ModelRetry` carrying the current revision, so a model holding stale context cannot overwrite a parameter the researcher just fixed. Counts are excluded from the fingerprint, so refreshing from WDK does not invalidate a held revision.

# The exposure

The Lead's `sub_agent_dispatch.build_strategy` calls `build_strategy_from_spec` directly and is **not** revision-guarded.

# Why it stayed, and what closed it

That call is the intentional "materialize my OperationalSpec" action. Gating it would have blocked legitimate builds, which is a worse failure than the one it prevents. The residual risk was real, and it was measured: a Lead rebuild reverted a hand-edited `min_expression_percentile` from 90 to 80 and changed every WDK step id.

The acceptance no longer applies, because the case it protected and the case it exposed are now different tools. `build_strategy` refuses a thread whose graph has steps, so it only ever materializes a spec where there is nothing to overwrite, and a revision guard on it would have nothing to guard. Every change to a strategy that exists goes through `edit_strategy`, which **is** revision-guarded: it reads `strategy_revision` before FRAME runs and refuses the commit if the strategy moved. See [an edit is a delta, not a rebuild](an-edit-is-a-delta-not-a-rebuild.md).

# Note for whoever changes this

Tool arguments are snake_case (`base_revision`), not camelCase. The error text must match the real argument name or it misleads the model into a retry loop. The same rule governs the refusal `build_strategy` now raises: it names `edit_strategy`, not `editStrategy`.

# Anchor

`ai/tools/standalone/strategy.py`, `sub_agent_dispatch.build_strategy`, `ai/lead/edit_dispatch.py`.
