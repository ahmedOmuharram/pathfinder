---
type: Backlog Item
title: After a hand edit in the graph editor, get_live_strategy_state returns the stale root count and no count for the edited step
description: The editor recomputes counts through POST /step-counts (root 15 became 7, step 1,456 became 752) but never writes them back; the step PATCH nulls only the edited step's estimatedSize and leaves its ancestors' counts as they were. read_live_state reads sync_state.step_counts, so the Lead tells the user "15 genes" for a strategy the UI shows returning 7.
tags: [investigation, ui-run, lead, live-state, counts, editor, staleness]
generated: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-17T00:00:00Z }
status: stable
---

# Investigation (UI run, 2026-08-17, PlasmoDB, conversation 4f69357c)

**What I did.** With a built 3-step strategy (2,122 INTERSECT 1,456 = 15), opened the full
editor, changed the Su percentile step's `min_expression_percentile` from 80 to 90, saved.
The editor showed 752 for the step and 7 for the root; the compact panel matched. Then
asked in chat: "How many genes does the strategy return right now, and has anything about
it changed since you last built it?"

**What I got.** `GET /api/v1/conversations/<id>` after the save:
`step_079c277b estimatedSize: null, min_expression_percentile "90"`, root `step_c42ab304
estimatedSize: 15`, `strategyRevision daac9e0704b82659`. The Lead called
`get_live_strategy_state` and replied: "The strategy currently returns 15 genes (the live
root/Combine result). ... Su et al. strand-specific RNA-seq filter: currently configured
for the top 20% in Gametocyte II or Gametocyte V; WDK did not provide a current estimate for
this step." It did say "The strategy was edited outside this conversation".

**Why that is wrong.** The number the user is told is the pre-edit number. This is the
same failure class the real-account UAT flagged as critical (the Lead quoting stale cached
counts); the "live" tool exists to prevent it and does not. The percentile is also
described as "top 20%" while the parameter it returned reads 90.

**Why it happens.** `ai/lead/live_state.py:read_live_state` reads
`session.sync_state.step_counts`; the editor's counts come from
`POST /api/v1/conversations/step-counts`, which executes the plan in WDK but does not
persist the counts, and the step-update path nulls the edited step's estimate without
invalidating its ancestors. Nothing in the read path asks WDK.

**Fix (to decide).** Either the step-update path invalidates every ancestor's estimate and
`read_live_state` fetches counts from WDK for any step whose estimate is null (it has the
WDK step ids), or the step-counts endpoint writes the counts it computed back into the
session so the persisted state is the one the UI shows. The Lead's reply should also state
the parameter values it read (90-100), not the display name's stale prose ("top 20%").

**What you would get.** "The strategy currently returns 7 transcripts; the Su step is now
top 10% (percentile 90-100) and returns 752."
