---
type: Decision
title: The eval harness is pydantic-evals, and the summary shape is ours
description: pydantic-evals ships with the pinned pydantic-ai and owns the dataset, the case loop, the evaluator protocol and the report; the machine-readable run summary is a local model, so a change of harness does not change the SLI feed. Building a runner from scratch was rejected as a reimplementation of an installed library; scoring by tree edit distance was rejected because the only implementation lives in the retired thesis harness and drags three numerical dependencies into the API image.
tags: [ws-v, evals, testing, observability]
generated: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-23T00:00:00Z }
status: stable
---

# The spike, and what it found

`pydantic-evals` arrives at the same version as `pydantic-ai`, which hard-depends
on `pydantic-ai-slim[evals]`. The runner imports it directly, so `apps/api`
declares it directly too (`pydantic-evals>=2.22.0,<3`): a transitive package that
a module imports by name is a dependency whether or not it is written down. It
provides `Case`, `Dataset`, an
`Evaluator` protocol over a typed `EvaluatorContext`, concurrency control,
per-case duration, a failure list that separates a raised task from a failed
assertion, and a report. That is the whole of what a runner needs.

It is used for exactly that. `pathfinder.devtools.eval_runner` builds a
`Dataset[EvalCase, ObservedOutcome, None]` whose task drives one real turn per
case, and whose single evaluator asks the corpus expectation.

# What stayed ours

**The summary.** `pathfinder.evals.summary.EvalRunSummary` is the run's
machine-readable result: harness, provider, assistant, timestamp, and one row
per case with its named differences. The observability contract reads this, and
it must not change shape because a library changed its report dataclass.

**The scoring.** `pathfinder.evals.scoring` is pure and unit-tested without a
database, a model or the harness. `score_case` returns every difference it
found, each naming the field, the expectation and the run's value, because a
boolean assertion answers "worse" without answering "how".

# What was rejected

**A runner written from scratch.** It would be a dataset loader, a case loop,
a concurrency limiter and a report - all of it already installed and already
tested upstream.

**A graded tree distance (NTED) instead of exact structural match.** An
implementation exists in `thesis/eval/scripts/tree_metrics.py`, and it is not
reusable here: the thesis harness is retired by this program, and the module
depends on `zss`, `numpy` and `scipy`, none of which the API image carries. The
corpus is four cases; a graded distance answers a question a four-case corpus
does not yet ask. V4 compares an id-free, parameter-free structural signature
and reports named differences. When the corpus is large enough that "close" is a
useful answer, the backlog item names the work.

# The limitation the runner states in its own docstring

With `PATHFINDER_CHAT_PROVIDER=mock` the model is a script. A run therefore
tests the **pipeline** - routing, materialisation, persistence, the shape the
phases assemble, and the verdict the turn reports - and not the model. It cannot
settle whether a real model would have chosen that route.

The case shape is provider-agnostic for exactly this reason: a real-model run is
the same corpus with a different provider flag, and the same expectations then
answer a stronger question.

# The promotion policy

Written into `conventions/verification-gates.md`, as ruled: an eval starts as a
tracked trend; it becomes a hard gate only after it catches or would have caught
a real regression and holds stable; a flaking gate is demoted or deleted, never
suppressed.
