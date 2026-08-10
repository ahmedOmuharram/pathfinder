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

# Why it stays

That call is the intentional "materialize my OperationalSpec" action. Gating it would block legitimate builds, which is a worse failure than the one it prevents. The residual risk is real: a Lead rebuild can still overwrite a hand edit.

`build_strategy` did gain `base_revision` for the case that could be guarded without cost: replacing a **non-empty** strategy without it raises `ModelRetry` pointing at `apply_operations`.

# Note for whoever changes this

Tool arguments are snake_case (`base_revision`), not camelCase. The error text must match the real argument name or it misleads the model into a retry loop.

# Anchor

`ai/tools/standalone/strategy.py` and `sub_agent_dispatch.build_strategy`.
