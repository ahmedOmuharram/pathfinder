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

# Second measurement (UI run 2026-08-17, VectorBase)

The moderate midgut-protease prompt (text OR GO proteases, midgut RNA-Seq filter, ortholog
transform to A. gambiae, colocation with `[TG].{5,6}YGCACACAN[TCA]H`): worker log
"sub-agent hit its usage ceiling; keeping partial progress" at tool_calls=60 against a
limit of 50, after about six minutes; ledger FRAME `criteria 0, bound 0`, so the partial
progress kept was nothing. The reply was honest ("the planning pass exhausted its
search-binding budget") and asked two good questions (conservation definition, motif
distance), which is the right behaviour once the budget is gone; the budget itself is the
defect. The Frame card also read "0 open questions" while the reply asked two.
The turn's usage footer read "16.7K tokens - $0.004" and the Frame card carried no token
or cost figure: a frame that hits the ceiling reports no usage at all, so the most
expensive turns are the ones the quota bar does not see.

# Why 60 is the wrong shape, not the wrong number

`PHASE_USAGE_LIMITS.tool_calls_limit = 60` in `ai/lead/sub_agent_tools.py` is a
constant. Binding one criterion cost roughly: `search_for_searches` →
`get_search_overview` → one or more `get_parameter_options` → `set_criterion`,
call it six to seven. Nine criteria is therefore ~60 before `set_structure` is
even reached, while a two-criterion problem finishes in about twenty.

The sheet now comes back from `set_criterion` itself
([one-proposer-one-validator](../decisions/one-proposer-one-validator.md)), so
the sequence is `search_for_searches` → `set_criterion` → `set_criterion`. The
per-criterion allowance below is unchanged and is now generous rather than
tight.

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

# The worse half is closed

Two things were already right and one was not.

`stream_sub_agent` (in `ai/lead/sub_agent_stream.py`) catches
`UsageLimitExceeded`, logs it as a budget rather
than a failure, and returns `None`; and `_apply_agent_state` runs after every
inner tool result, so the draft the sub-agent has been writing is already in
`deps.state.operational_spec` when the ceiling fires. The criteria were never
actually lost.

What was lost was the report. `frame_problem` turned that `None` into
`FrameResult(summary="FRAME returned no result.")`, so the Lead was told nothing
had happened and the eight bound criteria were invisible to it.
`frame_result_from_draft` now reads the draft and names them, so the turn ends
with "eight bound, ask me to continue" rather than with silence.

# The scaling half is closed

Three shapes were available: the Lead declaring a size before dispatch, FRAME
re-dispatched per criterion, or a limit raised mid-run. The third is not
possible - a per-run `UsageLimits` is fixed when the run starts - and the second
buys per-criterion isolation at the price of re-establishing context for each
one. The first is the least machinery, and the Lead is the only place that has
the goal text before FRAME runs.

`frame_problem` now takes `expected_criteria`, and `phase_usage_limits` turns it
into a ceiling of `criteria * 7 + 8`, held between 40 and 160. The floor keeps a
small problem able to recover from one wrong search; the cap is what stops an
overstated count from spending a whole turn. A count that is too low is no
longer fatal either, because the partial-progress report above turns exhaustion
into "these are bound, ask me to continue".

The estimate is the model's, so it can be wrong. That is acceptable here and it
would not have been before: both directions now degrade rather than fail.

# Anchor

`phase_usage_limits` in `ai/lead/sub_agent_tools.py` and `expected_criteria` on
`frame_problem`. Done when the nine-criterion prompt either completes or returns
its bound criteria with a clear statement of what remains, and when the budget
is a function of the declared criteria rather than a constant.
