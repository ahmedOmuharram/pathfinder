---
type: Backlog Item
title: FRAME's tool budget does not scale with the problem, and a run that hits it loses everything
description: Nine criteria do not fit in a fixed 60 tool calls. Hitting the ceiling discards the criteria already bound, which is the same discard-on-a-recoverable-condition pattern fixed for the WDK 5xx.
tags: [agents, budget, resilience]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# Symptom

The multi-criterion drug-target prompt, live PlasmoDB, in the browser:

> The next tool call(s) would exceed the tool_calls_limit of 60 (tool_calls=61).

This now surfaces honestly rather than as a crash (see
[suppression-follows-the-call-not-the-chunk-type](../decisions/suppression-follows-the-call-not-the-chunk-type.md)),
but the turn still ends with nothing built.

# Why 60 is the wrong shape, not the wrong number

`PHASE_USAGE_LIMITS.tool_calls_limit = 60` in `ai/lead/sub_agent_tools.py` is a
constant. Binding one criterion costs roughly: `search_for_searches` →
`get_search_overview` → one or more `get_parameter_options` → `set_criterion`,
call it six to seven. Nine criteria is therefore ~60 before `set_structure` is
even reached, while a two-criterion problem finishes in about twenty.

The budget does not scale with the work the spec has declared, so the same
number is generous for a small problem and impossible for a large one. Raising
the constant moves the boundary; it does not remove it.

# The worse half

A run that hits the ceiling discards the criteria it already bound. In the
observed run FRAME had operationalized eight of nine before dying. That is the
same shape as the WDK 5xx that abandoned a whole criterion
([contextualizing-params-is-an-enrichment](../decisions/contextualizing-params-is-an-enrichment.md)):
a recoverable condition costing everything upstream of it.

Partial progress should survive. FRAME returning "here are the eight I bound,
the ninth needs another pass" is a usable turn; losing all nine is not.

# Anchor

`PHASE_USAGE_LIMITS` in `ai/lead/sub_agent_tools.py`, and the FRAME sub-agent's
result path. Done when the nine-criterion prompt either completes or returns its
bound criteria with a clear statement of what remains, and when the budget is a
function of the declared criteria rather than a constant.
