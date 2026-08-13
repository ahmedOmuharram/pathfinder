---
type: Backlog Item
title: EXPIRED and INTERRUPTED are treated as fatal although WDK asks for a re-run
description: WDK flags six execution statuses requiresRerun and re-executes exactly those when the result path is posted again. PathFinder re-runs three of them and raises on EXPIRED and INTERRUPTED, so a recoverable failure ends the enrichment instead of retrying it.
tags: [wdk-alignment, integrations, step-analyses, reliability]
generated: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-10T00:00:00Z }
status: stable
---

# The defect

`_poll_analysis` in
`apps/api/src/pathfinder/integrations/veupathdb/strategy_api/analyses.py` splits
step-analysis statuses three ways. `COMPLETE` returns. `EXPIRED` and
`INTERRUPTED` raise immediately, at lines 149-153, with no re-run attempted. And
`_RETRIABLE_STATUSES`, which is `{ERROR, OUT_OF_DATE, STEP_REVISED}`, re-runs the
instance up to `max_retries`.

WDK disagrees about the middle branch, and it is not a matter of interpretation:
`requiresRerun` is the flag the platform itself branches on. The upstream
behavior and its pinned citations are
[WDK-VALID-009](../wdk/rules/validation.md). Six of the eleven statuses carry it
- `CREATED`, `STEP_REVISED`, `INTERRUPTED`, `ERROR`, `EXPIRED`, `OUT_OF_DATE` -
and `StepAnalysisFactoryImpl.runAnalysis` re-executes exactly those, resetting
the execution to `PENDING`. PathFinder acts on three of the six and raises on
two of the remaining three.

# What actually goes wrong, and what does not

The consequence is bounded and this item is ranked on the bounded version. An
enrichment that WDK was willing to run again instead ends as a failure, and the
work already done - building the step, materialising its answer, creating the
instance - is discarded. The two statuses describe conditions that a second
attempt can genuinely clear:

- `EXPIRED` means the plugin exceeded the timeout the site model configured for
  it. A re-run on a warm cache, or at a quieter moment, can finish.
- `INTERRUPTED` means the server shut down or the run was cut off mid-flight. It
  says nothing about the data and a re-run is the obvious response.

**The message raised on this path is accurate and this item does not claim
otherwise.** It reads `Analysis {analysis_id} ended with status: {status}`,
which is exactly what happened. An earlier draft of this item asserted that the
researcher is told their gene set is inadequate; that was a misattribution
between two different raises in the same function and it is wrong. The gene-set
sentence lives at lines 164-172, on the retries-exhausted branch, and is
therefore reachable only from `ERROR`, `OUT_OF_DATE` and `STEP_REVISED` - never
from `EXPIRED` or `INTERRUPTED`. The correction is recorded here rather than
silently applied, because a backlog item that overstates its own severity is
worse than no item.

So: a researcher sees a failed enrichment with a truthful explanation, and the
correct response - ask again - is available to them manually. Nothing is
silently wrong, no number is corrupted, and no false cause is argued. That is
why this sits below the silent-result items on the index rather than at the top
of it.

# A separate, smaller observation on the other branch

Worth recording while the function is open, and deliberately not folded into the
headline because it is a different defect on a different path.

The retries-exhausted message asserts a cause: "This typically happens when the
gene set is too small or lacks the required annotations." That is a plausible
reading of `ERROR`. It is not a plausible reading of `OUT_OF_DATE`, which means
the result cache was purged, or of `STEP_REVISED`, which means the step changed
- neither has anything to do with the size or annotation of a gene set. Since
all three reach the same sentence, two of them get a diagnosis that is a guess.

This is a smaller problem than it first looks: reaching that line requires three
re-runs to have already failed, so it is rare, and unlike the statuses above it
at least fires on a genuinely exhausted condition. Fix it on the same pass by
attaching the explanation to the status that supports it, but do not let it
carry the ranking of this item.

# How to confirm

Both headline statuses are hard to provoke live - one needs a plugin to exceed
its timeout, the other a server restart mid-run - which is why
[WDK-VALID-009](../wdk/rules/validation.md) is the one rule in its file with no
live confirmation. Do not build the fix around reproducing them.

Confirm at the unit level. `_poll_analysis` takes its status from
`self.client.get_analysis_status`, so a stub client yielding `EXPIRED` then
`COMPLETE` is enough: today the first value raises, and the assertion to write
is that it re-runs and then succeeds. The transport stubs under
`apps/api/src/pathfinder/tests/unit/integrations/veupathdb/` are the pattern -
`test_http_session_reinit.py` is the closest.

The upstream half is confirmed by reading rather than running: `ExecutionStatus`
and `StepAnalysisFactoryImpl.runAnalysis` are both cited from the pinned sha in
[WDK-VALID-009](../wdk/rules/validation.md).

# Where to look, and the shape of the fix

`_RETRIABLE_STATUSES` and `_poll_analysis` in
`integrations/veupathdb/strategy_api/analyses.py`. Three things the fix should
get right:

- **Mirror `requiresRerun` rather than curating a set.** The six statuses are a
  property of the platform, and a hand-maintained subset in PathFinder has
  already drifted from it once. A frozenset naming all six with a comment
  pointing at the rule is the minimum; a status model carrying the flag is
  better.
- **Do not let `EXPIRED` retry forever.** It is the one status where repeating
  an identical request is genuinely likely to repeat the outcome, so it needs a
  bound - a smaller retry budget, not a fatal branch.
- **Attach each message to the condition it describes.** The current
  `EXPIRED`/`INTERRUPTED` text is correct and should survive; the
  retries-exhausted text should stop asserting a gene-set cause for statuses
  that cannot have one.

Per the repo's TDD rule the failing test comes first.

# Anchor

`_RETRIABLE_STATUSES` and `_poll_analysis` in
`integrations/veupathdb/strategy_api/analyses.py`. Done when all six
`requiresRerun` statuses re-run, `EXPIRED` carries its own bound, no raised
message asserts a cause the status does not support, and a test asserts the
`EXPIRED`-then-`COMPLETE` path.
