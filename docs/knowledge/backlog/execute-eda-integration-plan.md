---
type: Backlog Item
title: Execute the EDA integration plan
description: The seven-batch plan at eda/plan/ is written and awaiting execution - conversational EDA analysis authoring, durable computes, the co-edited notebook tab with ECharts visualizations, and step export. Each batch runs implementer subagents, per-pair verifiers, and a session-lead close per the plan's verification protocol.
tags: [eda, plan, integration, execution]
generated: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
status: stable
---

**What this is.** The EDA bundle is a finished specification
([../eda/](../eda/index.md)); the implementation plan sits at
[../eda/plan/](../eda/plan/index.md) with an
[overview](../eda/plan/overview.md) (pinned contract, layering, verification
protocol) and seven batch documents carrying per-implementer task cards.

**What remains.** All seven batches: integration foundation, services and
catalog, conversational backend, transport and types, charts and state, the
EDA tab, chat co-editing and e2e. Batches close in order; a batch closes only
when its verifiers' reports are re-verified by the session lead and the full
gate ladders are green.

**Remove this item** in the same change that closes batch 7, per the bundle
rule that a finished backlog is an empty backlog.
