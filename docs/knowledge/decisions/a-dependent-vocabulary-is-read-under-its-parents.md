---
type: Decision
title: A dependent vocabulary is read under the parents already bound
description: get_parameter_options with no context returned WDK's default profileset, so the model was shown HB3's time points for a criterion bound to 3D7 and correctly reported hours that genuinely do not exist in what it was shown.
tags: [agents, parameters, wdk-alignment]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# What was decided

`get_parameter_options` inherits the parent values the draft spec has already
bound for that search (`AgentToolState.resolved_params_for`). An explicit
`context_values` argument still wins, because that is the model deliberately
exploring a different parent.

# Why

A dependent param's vocabulary is only meaningful under its parents, and WDK
answers with the search's DEFAULTS when no context is supplied. Those are not
cosmetic variations of one list. The three DeRisi profilesets are different
experiments with different time courses:

| profileset | leaves | hours absent from 1-48 |
|---|---|---|
| DeRisi 3D7 Smoothed | 46 | 47, 48 |
| **DeRisi HB3 Smoothed** (the search default) | 46 | **23, 29** |
| DeRisi Dd2 Smoothed | 45 | 8, 44, 48 |

The criterion was bound to 3D7. The read went out with no context, so WDK
returned HB3's list. The model asked for hours 20-32, observed that 23 and 29
were absent, and reported the criterion unsatisfiable.

**It was right about what it was shown.** The tool showed it the wrong dataset.
No amount of prompting fixes that, and nothing in the response distinguished
this list from the correct one -- both are 46 plausible time points.

# The note had to change too

The note previously said the values were "for the default context only". That
stops being true once a read inherits bound parents, and a note that lies about
which dataset produced a list is worse than no note. It now names the applied
context and warns that another parent yields a different list.

# Evidence

Observed: same call, before and after:

| read | 23 Hour | 29 Hour | 47 Hour | 48 Hour |
|---|---|---|---|---|
| no context (before) | absent | absent | present | present |
| inherits bound parent (after) | present | present | absent | absent |
