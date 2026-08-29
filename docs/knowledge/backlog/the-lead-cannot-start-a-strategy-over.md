---
type: Backlog Item
title: The Lead has no way to throw a strategy away, so "start over" has no tool behind it
description: "`build_strategy` now refuses a thread that already has a strategy, and `edit_strategy` only changes one. `clear_strategy` exists and requires approval, but it is registered only in the execution toolset, which the Lead reaches solely through `recover_failed_steps`. A user who asks to scrap the strategy and begin again gets prose and nothing else."
tags: [agents, lead, strategy, tool-surface]
generated: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
status: stable
---

# What I did

Added the `build_strategy` refusal (a thread with steps is an edit, not a
build), wrote its retry text to point the model at `clear_strategy` as the
deliberate destructive path, and ran the tool-surface gate:

```
cd apps/api && uv run pytest src/pathfinder/tests/unit/ai/test_tool_surface_agreement.py -q
```

# What I got

```
E       AssertionError: lead instructions name uncallable tools: ['clear_strategy']
E       assert not ['clear_strategy']
```

`grep -rn "clear_strategy" apps/api/src/pathfinder --include="*.py"` shows one
registration, `ai/tools/toolsets/execution.py:119`
(`Tool(clear_strategy, requires_approval=True, max_retries=3)`). The execution
toolset is opened by exactly one Lead dispatch, `recover_failed_steps`, whose
docstring restricts it to `ledger.build.needs_recovery is True`.

# Why that's wrong

The refusal is correct and the alternative it names is unreachable. A researcher
who says "scrap this and start again with a different approach" now gets a
sentence and a strategy that is still there; the only way to clear it is the
graph editor, by hand, step by step. The retry text was reworded to stop naming
the tool, so the Lead is told to ask the user and then has nothing to do with
the answer.

# Why it happens

`clear_strategy` takes `RunContext[AgentDeps]`, and the Lead's tools take
`RunContext[LeadDeps]`, so it cannot simply be added to `build_lead_agent`'s
tool list. It also carries `requires_approval=True`, and `consult_user` is
currently the only approval-required Lead tool
(`tests/unit/ai/lead/test_lead_agent_seam.py::test_only_the_consult_tool_still_asks_for_approval`),
so registering it changes the Lead's approval surface and the card the frontend
renders for it.

# Fix

A thin Lead wrapper `clear_strategy(ctx: RunContext[LeadDeps], confirm: bool)`
that builds `AgentDeps` through `agent_deps_for` and delegates to the standalone
tool, registered with `requires_approval=True`. Then decide what the approval
card says for a destructive whole-strategy delete, update the seam test's
expected deferred-tool list, and put the tool name back in
`build_would_replace_the_strategy` and in the Lead's instructions.

# What you'd get

"Scrap this and start again" reaches an approval card naming what will be
deleted; the user answers; the Lead frames and builds fresh. The refusal text
can then name the tool that does it.
