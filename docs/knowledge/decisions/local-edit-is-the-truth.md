---
type: Decision
title: The local edit is the truth; a rejected step is that step's problem
description: A WDK push rejection is reported per step in a 200 rather than raised as a 502 that the client rolls back.
tags: [strategy-graph, transport, r5]
generated: { by: claude-code/opus-5, at: 2026-08-09T00:00:00Z }
verified: { by: human:ahmedOmuharram, at: 2026-08-09T00:00:00Z }
status: stable
---

# The bug this fixes

The order was already apply, then push, then persist. The inconsistency was the **shape of the failure**: `PartialPushError` (502) was raised after the edit had been applied in memory and written to Postgres. The client's `onError` rolled the optimistic cache back and showed "Operation failed", while the server had kept the change and handed it straight back on the next read.

Memory, Postgres, WDK and the canvas told four different stories.

# The decision

A WDK rejection is that **step's** problem, not a failure of the operation. `CommitResult.failed_step_ids` is reported instead of raised, so the response is a 200 the client adopts. `StrategyAst.wdk_push_errors` makes the rejection durable across a reload, and `StepResponse.wdk_push_error` carries it per step.

# What was deleted

Two pieces of machinery were dead once the raise went, and leaving them would have implied the old contract still existed:

- `PartialPushError` itself.
- `ConversationRepository.commit_partial()`, which existed solely to make partial state durable before raising it.

# The frontend half mattered as much

`wdkPushError` was declared on `StepResponse` and populated **nowhere**, consumed **nowhere**. A rejected step was invisible. It now flows through `StepSnapshot.wdkPushError` into `ValidationBanner`, which had to stop gating on `isInvalid || isFailed`: the push fails on the server, so no local lifecycle transition happens and the banner never rendered.

# Anchor

`services/strategies/commit.py` (`CommitResult.failed_step_ids`) and `ValidationBanner`. Verified by 45 live-WDK tests.
