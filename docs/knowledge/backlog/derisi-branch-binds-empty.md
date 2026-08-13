---
type: Backlog Item
title: The DeRisi expression branch binds to zero genes where a looser binding gave a large result
description: With the request's own values bound rather than WDK's defaults, the top-10% trophozoite branch returns 0. The strategy still builds through the OR arm, and the agent correctly refuses to verify - but an empty branch is not obviously right.
tags: [agents, parameters, wdk-alignment]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# Symptom

Observed on a multi-criterion request. The strategy **builds** -- the built strategy,
16 steps, the intended genes -- and the agent then stops:

> the DeRisi microarray branch returned 0 genes after applying the top-10%
> expression criterion in the 20-32-hour trophozoite window. I therefore stopped
> before verification rather than report an incomplete or misleading candidate
> list.

That refusal is right, and it is the behaviour this week's work was for. The
empty branch underneath it is the open question.

# Why it is suspicious

An earlier, looser run of the same criterion returned **a large result** genes. That run
took WDK's default `min_expression_percentile` of 80 (the top *20* percent) and
WDK's default sample selection. This run binds what the request actually says:
the top 10 percent, over thirteen named hour terms.

So the drop from a large result to 0 has at least three candidate causes and they are not
distinguishable from the outside:

1. **`any_or_all`.** If this param is bound to "all", the search demands a gene
   sit in the top decile in *every one* of thirteen hours. That could legitimately
   be zero, and it is not what "expressed during the trophozoite stage" means.
2. **The percentile bound.** 90-100 is a real tightening over 80-100 and would
   reduce the count, though not obviously to zero.
3. **A wrong sample binding**, if the thirteen terms are not the ones the
   profileset actually offers.

# The check that settles it

Read the built step's `searchConfig.parameters` from the built strategy
and record `min_expression_percentile`, `any_or_all`, and the length of
`samples_percentile_generic`. Then re-run the same search varying only
`any_or_all` between "any" and "all". That single comparison separates cause (1)
from (2) and (3), and it is one live call.

The parameters were not captured in this run's retained logs, which is itself
worth fixing: a bound step's parameters are the first thing anyone needs when a
branch returns zero.

# Anchor

The DeRisi criterion in `services/catalog/param_dag.py` resolution, and whatever
sets `any_or_all` -- it is a scalar-defaultable single-pick, so it currently
takes WDK's default without the request ever being consulted. Done when the
branch's count is explained, and when a bound step's parameters are recoverable
from a run.
