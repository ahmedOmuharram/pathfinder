---
type: Plan
title: EDA integration plan overview
description: The layered plan that brings EDA into PathFinder - conversational analysis authoring, durable computes, a co-edited notebook tab with real visualizations, and step export - in seven verified batches.
tags: [eda, pathfinder, plan, batches, integration]
generated: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
status: accepted
---

# EDA integration plan overview

> For agentic workers: implement batch by batch, task by task, per the batch
> documents in this directory. Every task follows red-green TDD and ends with
> its gates green. Do not start a batch before the prior batch's verifier
> reports are accepted.

**Goal:** A researcher can explore an EDA study in conversation and in a
workbench-style tab at once - subset it with live counts, run differential
expression as a durable background compute, see the volcano and the PCA as
real charts inline in chat and in the tab, and export the thresholded gene
set as an ordinary step into their current strategy.

**Spec:** [../pathfinder-architecture-fit.md](../pathfinder-architecture-fit.md)
is the architecture this plan implements; the semantics it builds on are the
rest of [the EDA bundle](../index.md), most heavily
[eda-wdk-bridge.md](../eda-wdk-bridge.md),
[computes-and-jobs.md](../computes-and-jobs.md),
[filters.md](../filters.md) and
[subsetting-and-tabular.md](../subsetting-and-tabular.md).

**Decisions taken with the user (2026-08-28):** both seams in one plan
(steps seam lands first, the tab builds on it); ECharts for statistical
charts (networks stay on the existing ReactFlow + elkjs); the analysis state
is a co-edited SSOT - agent tools and tab clicks mutate the same analysis,
and chat renders it live.

## The shape in one paragraph

EDA enters PathFinder as one integration client, one domain module of pure
predicates, one service package, one agent toolset plus one durable tool, one
transport router, one `data-eda.*` part namespace, one persistence table
holding references, one chart foundation in `lib/`, one feature tab, and one
set of conversation part renderers. Nothing new architecturally: every piece
copies a pattern that already exists for WDK (typed client, catalog
embeddings, sheet-validated authoring, `@durable_tool` jobs, stream parts,
`conversation_strategies`-style attachment, workbench-style feature).

## Layering (who may import whom)

```
transport/http/routers/eda.py ──> services/eda/* ──> domain/eda.py
ai/tools/standalone/eda_*.py  ──> services/eda/*      integrations/eda/*
jobs/impls/eda_compute_impl.py──> services/eda/*  ──> persistence
features/eda + features/conversation ──> state/eda + lib/api + lib/components/charts
```

Enforced by the existing import-linter contracts (`apps/api/pyproject.toml`)
and `apps/web/scripts/check-boundaries.mjs`. Nothing EDA-shaped enters
`packages/assistant-core`; the runtime seams used are the open stream-part
registry and, later, an admitted tool source - both already generic.

## The co-edited SSOT

One conversation binds at most one open EDA analysis at a time. The upstream
EDA user service is the SSOT for the analysis document, exactly as WDK is for
a strategy:

- `open_eda_analysis` creates the upstream analysis
  (`POST /eda/users/{uid}/analyses/{project}`) and writes one
  `conversation_analyses` row: `(conversation_id, site_id, dataset_id,
  analysis_id)`. PathFinder never stores the descriptor.
- Every mutation - an agent's `set_eda_filters`, a click in the subset cell -
  goes through `services/eda/authoring.py`, which PATCHes upstream and emits
  a `data-eda.analysis-state` chunk, so both surfaces re-render from the same
  event.
- The tab hydrates from `GET /api/v1/conversations/{id}/eda` plus the
  conversation's event snapshot; chat renders the same parts.
- `create_eda_step` serializes the descriptor once
  (`model_dump_json(by_alias=True, exclude_none=True)`) into
  `eda_analysis_spec` and creates the WDK step through the existing strategy
  service. The step is then upstream's problem, like every other step.

## The pinned shared contract

Both drafting tracks and every implementer use these exact names. A batch
document may refine a signature; it may not rename anything here.

**Agent tools** (`apps/api/src/pathfinder/ai/tools/standalone/`):
`search_eda_studies`, `describe_eda_study`, `open_eda_analysis`,
`set_eda_filters`, `preview_eda_subset`, `run_eda_compute` (durable),
`create_eda_step`.

**Stream part kinds** (backend registry and `DataPartKind` in
`packages/shared-ts/src/types.ts`): `data-eda.analysis-state`,
`data-eda.subset-preview`, `data-eda.viz`.

**Transport** (`apps/api/src/pathfinder/transport/http/routers/eda.py`):
`GET /api/v1/eda/studies?q=`, `GET /api/v1/eda/studies/{dataset_id}`,
`POST /api/v1/eda/count`, `POST /api/v1/eda/distribution`,
`POST /api/v1/eda/viz`, `GET|PATCH /api/v1/conversations/{id}/eda`.

**Persistence:** table `conversation_analyses`
(`conversation_id, site_id, dataset_id, analysis_id, revision, created_at`;
`revision` is the per-binding mutation counter every analysis-state part
carries), repository
`ConversationAnalysesRepository`, alembic migration in `apps/api`.

**Python packages:** `pathfinder.integrations.eda` (`models.py`, `client.py`,
`analyses.py`), `pathfinder.domain.eda`, `pathfinder.services.eda`
(`catalog.py`, `authoring.py`, `compute.py`),
`pathfinder.jobs.impls.eda_compute_impl`.

**Frontend:** charts in `apps/web/src/lib/components/charts/` (`EChart.tsx`
base plus `VolcanoChart.tsx`, `HistogramChart.tsx`, `BarChart.tsx`,
`ScatterChart.tsx`; a boxplot chart left the contract at plan time because no
settled payload carries fences and nothing consumes it); store
`apps/web/src/state/eda.ts`
(`useEdaStore`); API wrappers `apps/web/src/lib/api/eda.ts`; the tab feature
under `apps/web/src/features/eda/` (`EdaWorkbench.tsx`, `StudyPicker.tsx`,
`cells/SubsetCell.tsx`, `cells/ComputeCell.tsx`, `cells/VizCell.tsx`,
`ExportStepButton.tsx`); chat renderers under
`apps/web/src/features/conversation/content/parts/` (`DataEdaViz.tsx`,
`DataEdaAnalysisState.tsx`, `DataEdaSubsetPreview.tsx`).

**Wire truths the code must encode** (from the bundle, all live-verified):
the spec's `studyId` field holds a DATASET id and must equal
`eda_dataset_id`; compute endpoints take the STUDY id; dataset-to-study
resolution goes through `/eda/permissions` only; a study needs exactly one
`VEUPATHDB_GENE_ID` variable to export genes; out-of-vocabulary filter values
return 200 with count 0, so the authoring validator is the only guard; date
bounds need `T00:00:00`; volcano rows may omit `pValue`; the compute job id
is a client-derivable MD5 shared across users; `resultsAll` gates row output;
user studies have an empty `sha1hash` (cache on `lastModified`).

## Batches

Seven batches, sequential. Within a batch, implementers run in parallel on
disjoint files. After batch 3 the conversational seam works end to end in
chat (text-only rendering); batches 4-7 add the tab and the charts.

| Batch | Document | Implementers | Verifiers |
|---|---|---|---|
| 1. Integration foundation | [batch-1-integration-foundation.md](batch-1-integration-foundation.md) | 3 | 2 |
| 2. Services and catalog | [batch-2-services.md](batch-2-services.md) | 3 | 2 |
| 3. Conversational backend | [batch-3-conversational-backend.md](batch-3-conversational-backend.md) | 3 | 2 |
| 4. Transport and types | [batch-4-transport-and-types.md](batch-4-transport-and-types.md) | 2 | 1 |
| 5. Charts and state | [batch-5-charts-and-state.md](batch-5-charts-and-state.md) | 2 | 1 |
| 6. The EDA tab | [batch-6-eda-tab.md](batch-6-eda-tab.md) | 2 | 1 |
| 7. Chat co-editing and e2e | [batch-7-chat-coediting-and-e2e.md](batch-7-chat-coediting-and-e2e.md) | 2 | 1 |

## The acceptance layer

A frozen, behavior-only conformance suite written BEFORE batch 1 opens, by QA
agents who will implement nothing. It exists because an implementer's own
tests can mirror the implementation; the acceptance layer cannot, because it
was written from the contract and the [EDA bundle's](../index.md)
live-verified values, with no code to mirror.

**Scope: stable boundaries only.** Service-function contracts (batch 2's
`serialize_spec`, `retained_summary`, the domain predicates), the seven HTTP
routes with the five-action PATCH union, part-payload round-trips and their
generated zod schemas, the store's public actions and reconcile rule, the
volcano selection's threshold behavior, and the three e2e journeys. Never
internals: no option-builder shapes, no private helpers, no repository SQL.
Assertions pin VALUES from the bundle (counts 4011/2501, the 202 body, the
5511/1543 volcano), never just shapes.

**Layout and gating.** Tests are pending until their batch closes, and the
tree stays green throughout:

- Backend: `apps/api/src/pathfinder/tests/acceptance/eda/`, one module per
  batch (`test_batch2_services.py`, ...). Every module opens with
  `pytest.importorskip` on the module it exercises (clean skip while the code
  does not exist) and carries `pytestmark = [pytest.mark.eda_acceptance]`;
  the marker is registered and deselected in the default `addopts`
  (`-m 'not llm and not eda_acceptance'`), so implementers' full-suite gates
  never run acceptance tests mid-batch. They are run explicitly -
  `uv run pytest -m eda_acceptance src/pathfinder/tests/acceptance/eda/ -v` -
  by an implementer who wants the signal, and by the lead at batch close.
- Frontend: `apps/web/src/acceptance/eda/`, files named `*.acceptance.ts` so
  the default vitest include (`src/**/*.{test,spec}.*`) never matches them;
  run explicitly via a dedicated config
  (`npx vitest run --config vitest.acceptance.config.ts`).
- E2E: `apps/web/e2e/acceptance/`, wired so a plain `npx playwright test`
  never executes it; run explicitly at batch 7's close.
- Acceptance tests self-contain their fixtures inline (MockTransport/MSW
  bodies embedded in the test file), so they never depend on an implementer's
  fixture files.

**The no-edit rule.** Implementers may not modify anything under the three
acceptance paths. Every verifier's FIRST check is a `diff -r` of each
acceptance tree against the lead's frozen baseline copy (the lead names its
location in the verifier brief; git is not used in this project's agent
work): any difference is an automatic FAIL. A genuinely
wrong acceptance test is escalated to the session lead with evidence; the
lead is the only party who edits the suite, and records the correction in the
batch report.

**The exit criterion this adds to EVERY batch:** the lead runs the batch's
acceptance module(s) and they pass unmodified -
`cd apps/api && uv run pytest -m eda_acceptance src/pathfinder/tests/acceptance/eda/test_batch<N>*.py -v --override-ini addopts=''`
for backend batches, the acceptance vitest config for batches 5-6, and the
acceptance playwright run for batch 7. A batch does not close on green
implementer tests alone.

## Verification protocol

Every batch runs the same three-ring protocol:

1. **Implementers** (Opus, one per task column, parallel, worktree-isolated
   when files could touch) follow their task cards exactly: failing test
   first, minimal implementation, targeted gates (ruff + mypy + pyright +
   affected pytest files on the backend; tsc + eslint + boundaries + affected
   vitest files on the frontend), then the full suite for their app.
2. **Verifiers** (one per two implementers) receive the implementers' claimed
   artifact lists and final reports. They re-run the FULL gate ladder from
   scratch, read every changed file, check each task card's steps against the
   diff, check the definition of done (zero debt, adjacent reconciliation,
   tests assert correctness not existence), and hunt for exactly the traps
   the batch document names. Two checks are universal, before any named trap:
   - **The acceptance no-edit check**: zero hunks under the acceptance paths
     (see The acceptance layer above).
   - **Mutation probes**: pick two or three behavior-bearing lines in the
     implementation (invert a threshold comparison, drop a filter from the
     array, skip a vocabulary check, swap a dataset id for a study id), apply
     each mutation, and run the implementer's tests. A mutation that no test
     kills is a FAIL: the tests assert shape, not behavior. Revert the
     mutations; the probe list and each one's killing test go in the report.
   A verifier's report lists PASS/FAIL per task with evidence, never a
   summary alone.
3. **The session lead verifies the verifiers**: re-runs the gates once more,
   spot-reads the diffs against the batch document, and accepts or reopens
   the batch. A batch is closed only by ring 3.

Live-EDA tests follow the `reference_wdk_live_test_suite` pattern: hermetic
tests run against recorded wire fixtures (checked in under the test tree);
live-lane tests are opt-in via environment flag and re-fetch to catch drift.

## Global constraints (inherited by every task)

- TDD is non-negotiable: no production code without a failing test first.
- Only the LLM is mocked (`PATHFINDER_CHAT_PROVIDER=mock`); EDA wire
  fixtures are recorded real responses, validated against the live API when
  the live lane runs.
- Pydantic maximalism at every boundary: `model_validate`, discriminated
  unions, `extra="ignore"`, `frozen=True` on fetched trees; no isinstance
  chains, no `dict.get` ladders, no type suppressions, no `import as`.
- Comments per the house rules: 1-3 lines, ASD-STE100, no narration, no
  history; near-zero new comments.
- ASCII punctuation only, in code strings and docs.
- React: no `useEffect`, no manual memoization (React Compiler). Imperative
  chart mounting uses ref callbacks and `ResizeObserver` teardown inside
  them.
- Frontend boundaries: `features/eda` imports only its own tree, `@/lib`,
  `@/state`, `@pathfinder/shared`, third-party. Charts live in `lib/` because
  two features render them.
- After backend changes: rebuild containers
  (`docker compose --env-file .env.dev up -d --build api worker web`) and
  verify the container actually updated before claiming anything works.
- When Pydantic schemas change: `yarn generate:types` from the repo root, and
  commit the regenerated output in the same task.
- Knowledge bundle discipline: docs updated in the same change that
  invalidates them; the backlog entry for this plan is removed by the task
  that finishes the work, not before.
