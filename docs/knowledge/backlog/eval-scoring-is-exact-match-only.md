---
type: Backlog Item
title: Eval scoring answers "same shape or not", so a strategy that is one operator away scores the same as one that shares no search
description: `score_case` compares an exact structural signature, so `((GenesByText UNION GenesByGoTerm) INTERSECT GenesByTaxon)` against `((GenesByText INTERSECT GenesByGoTerm) INTERSECT GenesByTaxon)` and against `GenesByLocation` are both simply "structure differs". A trend drawn from that cannot say whether a change made the assistant slightly worse or completely wrong. The repo's only tree-edit-distance implementation is in the retired thesis harness and depends on zss, numpy and scipy.
tags: [evals, ws-v, scoring, metrics]
generated: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
status: stable
---

# The gap

`pathfinder/evals/scoring.py` signs a strategy as a string - search names and
operators, ids and parameter values dropped - and compares the two strings. The
difference report names the field and both values, which is enough to read a
single failure by hand.

It is not enough to draw a trend from once the corpus grows. Two failures that
are a world apart produce the same row:

| expected | produced | reported |
|---|---|---|
| `((GenesByText UNION GenesByGoTerm) INTERSECT GenesByTaxon)` | `((GenesByText INTERSECT GenesByGoTerm) INTERSECT GenesByTaxon)` | `structure` differs |
| `((GenesByText UNION GenesByGoTerm) INTERSECT GenesByTaxon)` | `GenesByLocation` | `structure` differs |

# Why it was left this way

[The harness decision](../decisions/the-eval-harness-is-pydantic-evals.md)
records it: an NTED implementation exists at
`thesis/eval/scripts/tree_metrics.py`, the thesis harness is retired by this
program, and the module needs `zss`, `numpy` and `scipy`, none of which
`apps/api` carries. Four cases do not need a graded answer.

# What to do when the corpus needs it

Decompose the way the thesis metric did - topology, search selection, full
labelled distance, then parameter fidelity on aligned nodes - and decide
deliberately whether the distance lives in `apps/api` (a new dependency in the
API image) or in a separate eval package that the runner imports. Then the
summary carries a per-case distance beside the boolean, and the trend can say
"worse by this much" rather than "different".

The trigger is a corpus where a human reading the difference list stops being
practical, or the first time a change is judged by an eval and the boolean does
not settle the argument.
