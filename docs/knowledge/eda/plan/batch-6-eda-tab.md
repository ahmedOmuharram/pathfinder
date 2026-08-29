---
type: Plan
title: "Batch 6: the EDA tab"
description: The workbench-style EDA feature - study picker, subset cell with live counts and filter popovers, compute cell driven by the idempotent run-compute action, viz cell with client-side volcano thresholds, and step export into the current strategy.
tags: [eda, pathfinder, plan, batch, frontend, feature, workbench]
generated: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
status: accepted
---

# Batch 6: the EDA tab

**Goal:** a researcher opens an EDA tab beside the chat, picks a study, subsets
it with live counts, runs differential expression, reads the volcano, and
exports the thresholded genes as a step into the strategy they are already
building.

**Prerequisites:** batch 5 closed. This batch consumes the charts in
`apps/web/src/lib/components/charts/`, the store in
`apps/web/src/state/eda.ts` and the wrappers in
`apps/web/src/lib/api/eda.ts`, all by the exact names batch 5 produced.

**Read before starting:**

- [overview.md](overview.md) - the pinned shared contract. Names there are law.
- [batch-5-charts-and-state.md](batch-5-charts-and-state.md) - its "settled
  contract" section and the Produces blocks of both its sections are this
  batch's whole input surface.
- [../data-model.md](../data-model.md) - the entity tree and the variable
  fields the tree browser renders.
- [../filters.md](../filters.md) - the seven filter types, their payloads, and
  their traps.
- [../subsetting-and-tabular.md](../subsetting-and-tabular.md) - count and
  distribution semantics, including cross-entity propagation.
- [../computes-and-jobs.md](../computes-and-jobs.md) - the differential
  expression config, the six job states, and the job id that is a hash of the
  request.
- [../visualizations.md](../visualizations.md) - why volcano thresholding is
  client side.
- [batch-7-chat-coediting-and-e2e.md](batch-7-chat-coediting-and-e2e.md) - what
  this batch must leave in place for the chat half.

## The settled contract this batch codes against

Quoted in full in
[batch-5-charts-and-state.md](batch-5-charts-and-state.md). The five facts that
shape this batch:

1. **`EdaEntityCount` carries both counts**:
   `{ entityId, entityDisplayName, count, unfilteredCount }`. Every count the
   tab shows is "count of unfilteredCount".
2. **A distribution is one `EdaDistributionSeries`**:
   `{ variableId, variableDisplayName, labels, values, subsetSize, numVarValues,
   numMissingCases, isMultiValued }`. Parallel arrays, no bin objects.
   `POST /api/v1/eda/distribution` returns exactly this, and so does the
   subset-preview part.
3. **`EdaAnalysisState.filters` is `unknown[]`.** The store has already parsed
   it with the generated `edaFilterSchema` and exposes `analysis.filters` as
   `EdaFilter[]` plus `analysis.unparsedFilterCount`. Editable chips read the
   parsed filters; an unparsed filter is reported, never hidden.
   `analysis.canExportRows` says whether the study can export genes.
   `studyDisplayName` is the study title and `displayName` is the analysis's own
   name.
4. **The viz part is a point cloud**:
   `{ datasetId, analysisId, chart, effectSizeLabel, effectSizeThreshold,
   significanceThreshold, effectDirection, totalPoints, retainedPoints, points }`
   where a point is
   `{ pointId, effectSize, pValue?, adjustedPValue?, retained }` with **numbers**.
   `chart` is one of `volcano | histogram | boxplot | bar | scatter`, and only
   `volcano` and `scatter` are renderable from a point cloud.
5. **`PATCH /api/v1/conversations/{id}/eda` is a five-member action union**:
   `bind`, `set-filters`, `run-compute`, `export-step`, `unbind`, answering
   `{ analysis, job, step }`. `taskId` is **null** for a tab-started compute, so
   the tab must not reach for `taskStatusOptions`. `run-compute` is an
   **idempotent submit-or-poll**: the job id is a hash of the request, so
   repeating the identical action is the status poll. The PATCH writes no
   conversation event; chat catches up on the agent's next analysis-state part.

## Inherited constraints

Copied here so no implementer needs another file.

**TDD is non-negotiable.** No production code without a failing test first.
Tests verify correctness (real counts, real field names, real vocabulary
values), not existence.

**React rules, enforced by `eslint.config.cjs`:**

- `useEffect` is banned by `no-restricted-imports`. Replacements the codebase
  already uses: a TanStack Query `queryFn` for a one-shot side effect
  (`features/conversation/content/parts/DataBackgroundTaskStarted.tsx` lines
  66-76), a render-time `setState` guarded by a comparison plus `queueMicrotask`
  for a cross-store write (`app/[siteId]/(app)/layout.tsx` lines 63-69,
  `features/conversation/rail/RightRail.tsx` lines 61-69), and a one-shot
  initialiser through `useState(() => ...)`
  (`app/[siteId]/workbench/page.tsx` line 10).
- `useMemo`, `useCallback` and `memo` are banned. React Compiler is on.
- `useState` for local UI state, Zustand for shared state, TanStack Query for
  anything the server owns.

**Other eslint rules that will fail a careless edit:**
`max-lines` 300 per file (blank lines and comments skipped) - the cells need
child components to stay under it,
`@typescript-eslint/strict-boolean-expressions`,
`@typescript-eslint/no-unnecessary-condition`,
`@typescript-eslint/switch-exhaustiveness-check`,
`consistent-type-imports` with inline type imports,
`no-console` except `warn` and `error`.

**tsconfig strictness:** `strict`, `noUncheckedIndexedAccess`,
`exactOptionalPropertyTypes`, `noPropertyAccessFromIndexSignature`. Indexing an
array or a `Record` yields `T | undefined`. An optional property cannot be
assigned `undefined`; omit the key with a conditional spread.

**No type suppressions.** No `as any`, `@ts-ignore`, `@ts-expect-error`,
`eslint-disable`. `as any` is also refused by `scripts/check-boundaries.mjs`
rule 2.

**No `import as`.**

**Frontend boundaries** (`scripts/check-boundaries.mjs`): a file under
`src/features/eda/` may import only relative paths inside `features/eda`,
`@/lib/...`, `@/state/...`, `@pathfinder/shared`,
`@pathfinder/assistant-client`, `@/components/ui/...`,
`@/components/ai-elements/...`, and third-party packages. It may **not** import
`@/features/strategy`, `@/features/conversation`, `@/features/workbench` or
`@/app`. No exemption is added to `CROSS_FEATURE_EXCEPTIONS` by this batch;
needing one means the code is in the wrong layer.

**API calls go through `lib/api/`.** A component never calls `fetch`. Every
EDA call in this batch goes through `apps/web/src/lib/api/eda.ts` from batch 5.

**Only the LLM is mocked.** Component tests use MSW against the real route
paths with recorded EDA payloads.

**Error handlers are not fallbacks.** A state that exists because a request
failed is named after its failure and routed through `toast.error` with
`toUserMessage` from `@/lib/api/errors`, exactly as
`features/strategy/mutations/useApplyOperation.ts` does. Never silently render
an empty list where an error happened.

**Comments:** 1 to 3 lines maximum, simple present tense. No narration, no
history, no dates, no names. Near zero new comments.

**ASCII punctuation only**, in code strings and prose. No em dash, no en dash,
no curly quotes, no unicode ellipsis. Use " - " and "...".

**Definition of done.** Gates green is not done. Done means zero debt from this
task, adjacent reconciliation, tests that assert the new behavior, and a recap
that leads with remaining debt.

**Gate ladder for every task in this batch:**

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
npx tsc --noEmit
npx eslint src/
node scripts/check-boundaries.mjs
node scripts/check-weak-assertions.mjs
npx vitest run <exact test files for this task>
```

At the end of a section, additionally `yarn format` then `npx vitest run`.

## The mount point, cited

The app has no tab-strip widget. A conversation-scoped full-pane surface is
mounted by three concrete edits, and the strategy canvas is the precedent for
all three:

1. **A route file** under the `(app)` group, which supplies the nav rail, the
   top bar and the conversation sidebar through
   `apps/web/src/app/[siteId]/(app)/layout.tsx`. The existing example is
   `apps/web/src/app/[siteId]/(app)/conversation/[conversationId]/strategy/page.tsx`,
   which is 16 lines: it reads `params` with `use()` and renders
   `<StrategyPage siteId={siteId} conversationId={conversationId} ... />`.
2. **A yield in `ChatShell`.**
   `apps/web/src/features/conversation/ChatShell.tsx` returns `null` when
   `isStrategyRoute(pathname)` is true, so the route's own `page.tsx` owns the
   main pane instead of the chat thread. The EDA route needs the same yield.
3. **A route helper** in `apps/web/src/lib/routes.ts`, whose header says never
   to inline a path.

The entry affordance is batch 7's: `DataEdaAnalysisState` grows an
"Open in EDA tab" link, and a right-rail EDA panel is added there. This batch
leaves the route reachable by URL and by batch 7's link.

## Wire truths from batches 4 and 5 (lead note; the wire wins over any sketch below)

Batch 4 shipped the routes and batch 5 wrapped them (`apps/web/src/lib/api/eda.ts`);
the generated Kubb names and the real shapes differ from several sketches in
this document, which were drafted before the routes existed. Where a task card
below contradicts these, the wire wins and the implementer says so in the report:

1. `POST /api/v1/eda/count` takes ONE `entityId` and answers
   `{entityId, count, unfilteredCount}`. There is no `entityIds` array and no
   `counts[]`; the subset cell calls `edaCount` once per entity it displays
   (the counts are independent reads of the same subset). The analysis state
   already carries every entity's counts at its revision, so the cell shows
   `analysis.entityCounts` until its own live counts arrive, and never an
   empty count.
2. `siteId` is a QUERY parameter on `/studies`, `/studies/{id}`, `/count`,
   `/distribution` and `/viz`; the batch-5 wrappers take one args object and
   split query from body, so callers pass `siteId` beside the body fields.
3. `POST /api/v1/eda/viz` also requires `conversationId` (query); it answers
   `EdaVizResponse` (`edaVizResponseSchema`), a different schema from the chat
   part's `EdaViz`.
4. `GET /api/v1/conversations/{id}/eda` answers `ConversationEdaResponse`
   (`conversationEdaResponseSchema`) and carries `analysis: EdaAnalysisState | null`
   (added as batch-4 reconciliation); hydrate the store from `analysis` exactly
   as a chat part does, never rebuild it from the flat fields.
5. The `run-compute` action's `computation` is `EdaComputationDescriptor`
   `{type, configuration}`, not `{appName, config}`; the job reference in the
   response is `{jobId, taskId, appName, status}`.
6. Generated type names: `EdaStudyListResponse`, `EdaStudyDetailResponse`,
   `ConversationEdaResponse`, `EdaVizResponse`, `PatchConversationEdaMutationRequest`
   (the union), `EdaAnalysisPatchResponse`; `EdaFilter` is imported from
   `@pathfinder/shared/generated/types/EdaFilter`; `@pathfinder/shared` re-exports
   `EdaSubsetPreview` and `EdaViz` as the part aliases.
7. The chart foundation's palette check (dataviz validator, batch 5) found
   three `--chart-*` slots under 3:1 contrast on the light ground; the charts
   ship a legend and a hover tooltip, and the RELIEF CHANNEL is this batch's:
   `VizCell` must offer a value readout beside every chart (the selected-gene
   list with effect size and p-value for the volcano; the point table for the
   scatter), never a chart alone. Batch 7's chat card inherits the same rule.
8. Exporting on a thread with no strategy BEGINS that strategy: the EDA step is
   the root and is pushed on that commit, exactly as the agent's first step is.
   Exporting beside an existing strategy adds a DETACHED second root that is
   persisted and not pushed, so the tab presents it as a draft with an attach
   affordance, never as pushed. See
   [the decision](../../decisions/an-eda-export-begins-the-strategy-when-none-exists.md)
   and the lead note before Task B4.
9. Every `EdaAnalysisState` field is required, on the wire and in the generated
   type; `revision` is `number | null`. The batch-5 store (`snapshotOf`) stays
   the one place that turns a payload into a snapshot, so every cell reads the
   analysis from `useEdaStore` and no consumer writes a `??` fallback.

## Implementer A: shell, study picker, subset cell

### Files

**Create**

- `apps/web/src/app/[siteId]/(app)/conversation/[conversationId]/eda/page.tsx`
- `apps/web/src/features/eda/EdaWorkbench.tsx`
- `apps/web/src/features/eda/StudyPicker.tsx`
- `apps/web/src/features/eda/cells/CellShell.tsx`
- `apps/web/src/features/eda/cells/SubsetCell.tsx`
- `apps/web/src/features/eda/cells/EntityTree.tsx`
- `apps/web/src/features/eda/cells/VariableRow.tsx`
- `apps/web/src/features/eda/cells/FilterChip.tsx`
- `apps/web/src/features/eda/cells/FilterEditor.tsx`
- `apps/web/src/features/eda/cells/DistributionSparkline.tsx`
- `apps/web/src/features/eda/filterDrafts.ts`

**Test**

- `apps/web/src/features/eda/filterDrafts.test.ts`
- `apps/web/src/features/eda/StudyPicker.test.tsx`
- `apps/web/src/features/eda/EdaWorkbench.test.tsx`
- `apps/web/src/features/eda/cells/SubsetCell.test.tsx`
- `apps/web/src/features/eda/cells/FilterEditor.test.tsx`

**Modify**

- `apps/web/src/lib/routes.ts`
- `apps/web/src/features/conversation/ChatShell.tsx`
- `apps/web/src/features/conversation/ChatShell.test.tsx`

### Interfaces

**Consumes** from batch 5:

```ts
import { BarChart } from "@/lib/components/charts/BarChart";
import { HistogramChart } from "@/lib/components/charts/HistogramChart";
import type { EdaCategorySeries } from "@/lib/components/charts/types";
import {
  conversationEdaOptions,
  countEdaSubset,
  edaDistribution,
  edaStudyDetailOptions,
  edaStudySearchOptions,
  patchConversationEda,
} from "@/lib/api/eda";
import { selectEffectiveFilters, useEdaStore } from "@/state/eda";
```

**Produces**, consumed by Implementer B and batch 7:

```ts
export function EdaWorkbench(props: {
  siteId: string;
  conversationId: string;
}): ReactElement;
export function CellShell(props: {
  title: string;
  subtitle: string | null;
  testId: string;
  actions?: ReactNode;
  children: ReactNode;
}): ReactElement;
export function collectEntityIds(root: EdaEntityNode | null): string[];
// lib/routes.ts
export function edaTabUrl(siteId: string, conversationId: string): string;
// features/conversation/ChatShell.tsx
export function isEdaRoute(pathname: string): boolean;
```

### The UX specification, concretely

**Route:** `/{siteId}/conversation/{conversationId}/eda`.

**`EdaWorkbench` layout**, one scrolling column inside the `(app)` shell's main
pane:

- A header row, sticky, `h-11`, `border-b border-border bg-card px-4`, with
  `data-testid="eda-workbench-header"`:
  - left: `analysis.studyDisplayName`, truncated, `text-sm font-medium`, and
    `analysis.displayName` beside it in `text-xs text-muted-foreground` when the
    two differ. When nothing is bound, the literal text "No study selected".
  - right: a "Change study" ghost button (visible only when bound) and the
    export button slot Implementer B fills.
- Body, `flex flex-col gap-4 p-4`:
  - **Unbound:** `<StudyPicker />` fills the body. No cells render.
  - **Bound:** three cells in order - `SubsetCell`, `ComputeCell`, `VizCell` -
    each wrapped in `CellShell`.

**"Change study"** calls
`patchConversationEda(conversationId, { action: "unbind" })` and then
`useEdaStore.getState().reset()`. The server drops the
`conversation_analyses` row, so a reload does not resurrect the old binding;
resetting the store alone would desync the two.

**`CellShell`** is a `<section>` with `data-testid`, a title row
(`text-xs font-medium uppercase tracking-wide text-muted-foreground`), an
optional subtitle line, an optional right-aligned `actions` slot, and a body in
`rounded-md border border-border bg-card p-3`.

**Named states.** Every non-happy state is a named component or a named notice,
never a bare empty div:

| State | Where | What renders |
|---|---|---|
| `EdaBindingPending` | workbench, while `conversationEdaOptions` is loading | `<Spinner className="size-5" />` centered, from `@/components/ui/spinner` |
| `EdaBindingError` | workbench, on query error | inline card with `data-testid="eda-binding-error"` naming the failure plus a Retry button calling `refetch`; also `toast.error(toUserMessage(error, "Could not read the EDA binding"))` |
| `EdaUnbindError` | workbench, when the unbind PATCH fails | `toast.error(toUserMessage(error, "Could not close the analysis"))`; the store is **not** reset, so the tab and the server stay in agreement |
| `StudyPickerIdle` | picker, query under 2 characters | "Type at least 2 characters to search studies." |
| `StudyPickerSearching` | picker, `isFetching` | `<Spinner className="size-4" />` beside the input |
| `StudyPickerEmpty` | picker, 0 results for a valid query | "No study on {siteId} matches {query}." |
| `StudyPickerSearchError` | picker, query error | `data-testid="eda-study-search-error"` plus Retry; `toast.error(toUserMessage(..., "Study search failed"))` |
| `StudyBindError` | picker, bind PATCH failed | `toast.error(toUserMessage(error, "Could not open the analysis"))`; the row stays clickable |
| `SubsetCountError` | subset cell, count or PATCH failed | `data-testid="eda-subset-count-error"`, the optimistic edit is rolled back, and `toast.error(toUserMessage(error, "Subset count failed"))` |
| `SubsetDistributionError` | subset cell, distribution failed | the sparkline area renders "distribution unavailable"; no toast, because the count already toasted |
| `SubsetUnparsedFiltersNotice` | subset cell, `analysis.unparsedFilterCount > 0` | `data-testid="eda-subset-unparsed-filters"`: "{n} filter(s) on this analysis cannot be edited here. Change them through chat." |
| `SubsetMultiValuedNotice` | sparkline, `distribution.isMultiValued` | "one record can carry several values, so these counts do not add up to the subset size" |
| `ExportBlockedNotice` | header, `analysis.canExportRows === false` | see Implementer B, Task B4 |

**`StudyPicker`:**

- A single text input, `data-testid="eda-study-search"`, placeholder
  "Search studies...", `aria-label="Search EDA studies"`, debounced with
  `useDebounce` from `use-debounce` at 250 ms. The undebounced value drives the
  input, the debounced value drives `edaStudySearchOptions`.
- Results as a `<ul data-testid="eda-study-results">` of `<li>` rows, each a
  `<button data-testid={"eda-study-row-" + datasetId}>` showing:
  `displayName` on line one; on line two, `shortDisplayName` when present, the
  `datasetId` in `font-mono`, and `lastModified` formatted with `date-fns`'
  `format(new Date(lastModified), "d MMM yyyy")`. `shortDisplayName` and
  `description` are **optional** on the wire - 14 of 759 live plasmodb rows omit
  `shortDisplayName` and 2 omit `description`
  ([../data-model.md](../data-model.md)) - so render neither unconditionally.
- Clicking a row calls
  `patchConversationEda(conversationId, { action: "bind", siteId, datasetId })`
  and on success calls
  `useEdaStore.getState().applyAnalysisState(response.analysis)` when
  `response.analysis` is not null.

**`SubsetCell`:**

- Left column, `w-72 shrink-0`, an `EntityTree`: one collapsible node per
  entity from `studyDetail.rootEntity`, recursing on `children`. A node shows
  `entityDisplayName`, its live count as "count of unfilteredCount", and, when
  expanded, its variables. Collapse state is local `useState<Set<string>>` keyed
  by entity id; the root entity starts expanded.
- Counts come from `liveCounts ?? analysis?.entityCounts ?? []`, where
  `liveCounts` is the last `countEdaSubset` result held in local state. Both are
  `EdaEntityCount[]`, so the row renders the same way whichever it reads.
- A variable list per expanded entity, rendered by `VariableRow`: `displayName`,
  a `type` badge, a `dataShape` badge when present, and a hint:
  - `type: "string"` with a `vocabulary`: "{n} values" plus the first three
    joined with ", ".
  - `type: "number"` or `"integer"`: `distributionDefaults.rangeMin` to
    `rangeMax` when both are present. All six `distributionDefaults` keys are
    optional on the wire; only three of six were live on
    `SEQUENCE_READ_COUNT` ([../data-model.md](../data-model.md)).
  - `type: "date"`: the same range, printed as the bare dates the metadata
    carries.
  - `type: "category"`: no hint, and the row is not clickable - a category
    carries no values.
  - A variable whose `hideFrom` contains `"everywhere"` or `"variableTree"` is
    not rendered. `hideFrom` is UI advice, not access control, and this is the
    UI.
  - A variable with `isMultiValued: true` shows the literal badge
    "multi-valued".
- Right column, `min-w-0 flex-1`: the filter chips, then the
  `SubsetUnparsedFiltersNotice` when there is one, then the selected variable's
  `DistributionSparkline`.
- Chips: one `FilterChip` per entry of `selectEffectiveFilters(state)`, each
  showing the variable display name and `filterSummary(filter)`, with an x
  button that removes it. Clicking the chip body reopens `FilterEditor` on it.
  The chips are built from the **parsed** filters the store exposes, never from
  the raw `unknown[]`.
- Every add, edit or remove:
  1. computes the next filter array,
  2. calls `setLocalFilters(next)` so the UI moves at once,
  3. fires `countEdaSubset` for every entity id in the tree,
  4. fires
     `patchConversationEda(conversationId, { action: "set-filters", filters: next })`,
  5. on success writes the counts into local state and calls
     `applyAnalysisState(response.analysis)`, which clears `localFilters`
     because the server document is now the truth,
  6. on failure calls `setLocalFilters(null)` and shows `SubsetCountError`.

**`DistributionSparkline`** takes the `EdaDistributionSeries` the distribution
route returned plus the selected variable's `dataShape`, and picks its form the
way the dataviz skill's form heuristic does:

- `dataShape: "continuous"` renders `HistogramChart` with `barMode="stack"`,
  `height={96}`, one series named "Subset".
- `categorical`, `ordinal`, `binary` or an absent `dataShape` renders
  `BarChart` with `barMode="group"`, the same height and series name.

Both take `series: [{ name: "Subset", labels: distribution.labels, values: distribution.values }]`,
which is `EdaCategorySeries` unchanged from the wire. Below the chart, one line:
`{numVarValues} of {subsetSize} records have a value`, and
`{numMissingCases} missing` when that is above zero. Read those three numbers
carefully: `subsetSize` is the subset's record count on the entity,
`numVarValues` is how many of them have a value, and a percentage against one
differs from a percentage against the other
([../subsetting-and-tabular.md](../subsetting-and-tabular.md)).

**`FilterEditor`** is a `Popover` from `@/components/ui/popover` whose body is
chosen by the variable's `type`:

| variable `type` | filter `type` | editor |
|---|---|---|
| `string` | `stringSet` | multi-select checkbox list over `vocabulary`; Apply disabled while nothing is checked |
| `integer`, `number` | `numberRange` | two number inputs seeded from `distributionDefaults.rangeMin` and `rangeMax` |
| `date` | `dateRange` | two date inputs seeded from `distributionDefaults.rangeMin` and `rangeMax` |
| `longitude` | not offered | the row is not clickable |
| `category` | not offered | the row is not clickable |

`numberSet`, `dateSet`, `longitudeRange` and `multiFilter` are **not** editable
in this batch. They are reachable through the agent's `set_eda_filters` and
render as read-only chips. Say so in the editor's footer text:
"Set membership and multi-filters are available through chat."

### Task A1: the route helper and the ChatShell yield

- [ ] **Failing test.** Add to
  `apps/web/src/features/conversation/ChatShell.test.tsx`:

```ts
import { isEdaRoute } from "./ChatShell";
import { edaTabUrl } from "@/lib/routes";

describe("isEdaRoute", () => {
  it("matches the conversation-scoped eda pane", () => {
    expect(isEdaRoute("/plasmodb/conversation/conv-1/eda")).toBe(true);
  });

  it("matches a nested eda path", () => {
    expect(isEdaRoute("/plasmodb/conversation/conv-1/eda/anything")).toBe(true);
  });

  it("does not match the chat thread itself", () => {
    expect(isEdaRoute("/plasmodb/conversation/conv-1")).toBe(false);
  });

  it("does not match a conversation whose id ends in eda", () => {
    expect(isEdaRoute("/plasmodb/conversation/conv-eda")).toBe(false);
  });
});

describe("edaTabUrl", () => {
  it("builds the site-scoped conversation eda path", () => {
    expect(edaTabUrl("plasmodb", "conv-1")).toBe("/plasmodb/conversation/conv-1/eda");
  });
});
```

- [ ] **Run and read the failure.**
  `npx vitest run src/features/conversation/ChatShell.test.tsx`
  Expected: `"isEdaRoute" is not exported by ... ChatShell.tsx`.

- [ ] **Implement.** In `apps/web/src/lib/routes.ts` add:

```ts
export function edaTabUrl(siteId: string, conversationId: string): string {
  return `/${siteId}/conversation/${conversationId}/eda`;
}
```

In `apps/web/src/features/conversation/ChatShell.tsx` add a second pattern
beside the existing `STRATEGY_PATH` and widen the yield:

```ts
const EDA_PATH = /\/conversation\/[^/]+\/eda(\/|$)/;

export function isEdaRoute(pathname: string): boolean {
  return EDA_PATH.test(pathname);
}
```

and change the existing guard from

```ts
  if (isStrategyRoute(pathname)) return null;
```

to

```ts
  // A route that owns the main pane renders its own page instead of the thread.
  if (isStrategyRoute(pathname) || isEdaRoute(pathname)) return null;
```

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/conversation/ChatShell.test.tsx src/lib/routes.test.ts`.

### Task A2: the study picker

- [ ] **Failing test.** Create
  `apps/web/src/features/eda/StudyPicker.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { useEdaStore } from "@/state/eda";
import { StudyPicker } from "./StudyPicker";

const BASE = "http://localhost:3000";
const server = setupServer();

const STUDY_ROW = {
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  displayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
  shortDisplayName: "Heat shock",
  lastModified: "2026-05-27T20:00:00-04:00",
  sourceType: "curated",
};

const ANALYSIS = {
  siteId: "plasmodb",
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  analysisId: "a-1",
  revision: 0,
  studyDisplayName: STUDY_ROW.displayName,
  displayName: "Unsaved analysis",
  numFilters: 0,
  numComputations: 0,
  filters: [],
  filterSummaries: [],
  entityCounts: [
    {
      entityId: "ENT_8151325d",
      entityDisplayName: "Sample",
      count: 12,
      unfilteredCount: 12,
    },
  ],
  canExportRows: true,
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => useEdaStore.getState().reset());

describe("StudyPicker", () => {
  it("asks for two characters before it searches", () => {
    render(<StudyPicker siteId="plasmodb" conversationId="conv-1" />);
    expect(screen.getByTestId("eda-study-picker")).toHaveTextContent(
      "Type at least 2 characters to search studies.",
    );
  });

  it("lists a matching study with its short name and dataset id", async () => {
    server.use(
      http.get(`${BASE}/api/v1/eda/studies`, () =>
        HttpResponse.json({ studies: [STUDY_ROW] }),
      ),
    );
    render(<StudyPicker siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.type(screen.getByTestId("eda-study-search"), "heat shock");
    const row = await screen.findByTestId("eda-study-row-DS_e973eadd57");
    expect(row).toHaveTextContent("Heat shock response in sensitive mutants");
    expect(row).toHaveTextContent("Heat shock");
    expect(row).toHaveTextContent("DS_e973eadd57");
  });

  it("renders a row that omits shortDisplayName without printing undefined", async () => {
    const { shortDisplayName, ...withoutShortName } = STUDY_ROW;
    server.use(
      http.get(`${BASE}/api/v1/eda/studies`, () =>
        HttpResponse.json({ studies: [withoutShortName] }),
      ),
    );
    render(<StudyPicker siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.type(screen.getByTestId("eda-study-search"), "heat shock");
    const row = await screen.findByTestId("eda-study-row-DS_e973eadd57");
    expect(row.textContent).not.toContain("undefined");
  });

  it("says which site and query found nothing", async () => {
    server.use(
      http.get(`${BASE}/api/v1/eda/studies`, () => HttpResponse.json({ studies: [] })),
    );
    render(<StudyPicker siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.type(screen.getByTestId("eda-study-search"), "zzzz");
    expect(
      await screen.findByText("No study on plasmodb matches zzzz."),
    ).toBeInTheDocument();
  });

  it("binds the analysis on click and hydrates the store", async () => {
    let patchBody: unknown = null;
    server.use(
      http.get(`${BASE}/api/v1/eda/studies`, () =>
        HttpResponse.json({ studies: [STUDY_ROW] }),
      ),
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ analysis: ANALYSIS, job: null, step: null });
      }),
    );
    render(<StudyPicker siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.type(screen.getByTestId("eda-study-search"), "heat shock");
    await userEvent.click(await screen.findByTestId("eda-study-row-DS_e973eadd57"));
    await waitFor(() => {
      expect(useEdaStore.getState().binding?.analysisId).toBe("a-1");
    });
    expect(patchBody).toEqual({
      action: "bind",
      siteId: "plasmodb",
      datasetId: "DS_e973eadd57",
    });
    expect(useEdaStore.getState().analysis?.entityCounts[0]?.unfilteredCount).toBe(12);
  });

  it("reports a failed search instead of showing an empty list", async () => {
    server.use(
      http.get(`${BASE}/api/v1/eda/studies`, () =>
        HttpResponse.json({ detail: "upstream is down" }, { status: 502 }),
      ),
    );
    render(<StudyPicker siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.type(screen.getByTestId("eda-study-search"), "heat shock");
    expect(await screen.findByTestId("eda-study-search-error")).toHaveTextContent(
      "upstream is down",
    );
  });
});
```

`vitest.setup.ts` already wraps every `render` in a `QueryClientProvider` with
retries off, so no wrapper is needed here.

- [ ] **Run and read the failure.**
  `npx vitest run src/features/eda/StudyPicker.test.tsx`
  Expected: `Failed to resolve import "./StudyPicker"`.

- [ ] **Implement** `apps/web/src/features/eda/StudyPicker.tsx`. Faithful
  sketch, under 300 lines:

```tsx
"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useDebounce } from "use-debounce";
import { format } from "date-fns";
import { toast } from "sonner";
import type { EdaStudySummary } from "@pathfinder/shared";

import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { toUserMessage } from "@/lib/api/errors";
import { edaStudySearchOptions, patchConversationEda } from "@/lib/api/eda";
import { useEdaStore } from "@/state/eda";

interface StudyPickerProps {
  siteId: string;
  conversationId: string;
}

export function StudyPicker({ siteId, conversationId }: StudyPickerProps) {
  const [typed, setTyped] = useState("");
  const [query] = useDebounce(typed, 250);
  const search = useQuery(edaStudySearchOptions(siteId, query));
  const applyAnalysisState = useEdaStore((s) => s.applyAnalysisState);

  const bind = useMutation({
    mutationFn: (datasetId: string) =>
      patchConversationEda(conversationId, { action: "bind", siteId, datasetId }),
    onSuccess: (response) => {
      if (response.analysis !== null) applyAnalysisState(response.analysis);
    },
    onError: (error) =>
      toast.error(toUserMessage(error, "Could not open the analysis")),
  });

  const trimmed = query.trim();
  return (
    <div data-testid="eda-study-picker" className="mx-auto w-full max-w-2xl">
      <div className="flex items-center gap-2">
        <Input
          data-testid="eda-study-search"
          aria-label="Search EDA studies"
          placeholder="Search studies..."
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
        />
        {search.isFetching && <Spinner className="size-4" />}
      </div>

      {trimmed.length < 2 ? (
        <p className="mt-3 text-xs text-muted-foreground">
          Type at least 2 characters to search studies.
        </p>
      ) : search.error !== null ? (
        <p
          data-testid="eda-study-search-error"
          className="mt-3 text-xs text-destructive"
        >
          {toUserMessage(search.error, "Study search failed")}
        </p>
      ) : search.data !== undefined && search.data.studies.length === 0 ? (
        <p className="mt-3 text-xs text-muted-foreground">
          {`No study on ${siteId} matches ${trimmed}.`}
        </p>
      ) : (
        <ul data-testid="eda-study-results" className="mt-3 divide-y divide-border">
          {(search.data?.studies ?? []).map((study) => (
            <StudyRow
              key={study.datasetId}
              study={study}
              onPick={() => bind.mutate(study.datasetId)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function StudyRow({ study, onPick }: { study: EdaStudySummary; onPick: () => void }) {
  return (
    <li>
      <button
        type="button"
        data-testid={`eda-study-row-${study.datasetId}`}
        onClick={onPick}
        className="w-full px-2 py-2 text-left hover:bg-accent"
      >
        <span className="block truncate text-sm">{study.displayName}</span>
        <span className="mt-0.5 block text-[11px] text-muted-foreground">
          {study.shortDisplayName != null && study.shortDisplayName !== "" && (
            <span className="mr-2">{study.shortDisplayName}</span>
          )}
          <span className="mr-2 font-mono">{study.datasetId}</span>
          <span>{format(new Date(study.lastModified), "d MMM yyyy")}</span>
        </span>
      </button>
    </li>
  );
}
```

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/eda/StudyPicker.test.tsx`.

### Task A3: filter drafts, the pure half of the subset cell

Every trap this task encodes is live-verified in
[../filters.md](../filters.md): a `stringSet` with an empty array is a 400
(`"String set filter: >0 strings must be specified"`); a bare `YYYY-MM-DD` date
bound is a **500**, not a 400, and the study metadata prints bare dates, so a
value copied out of `distributionDefaults` must gain `T00:00:00`; an
out-of-vocabulary `stringSet` value returns 200 with count 0, so nothing
upstream corrects a typo; two filters on the same variable compose by AND, so
replacing rather than appending is the only sane edit.

- [ ] **Failing test.** Create
  `apps/web/src/features/eda/filterDrafts.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  collectEntityIds,
  edaDateBound,
  filterSummary,
  filterableVariableType,
  isDraftApplicable,
  removeFilter,
  upsertFilter,
} from "./filterDrafts";

const FEBRILE = {
  entityId: "ENT_8151325d",
  variableId: "VAR_081ab087",
  type: "stringSet" as const,
  stringSet: ["febrile"],
};

describe("edaDateBound", () => {
  it("appends the time part the service requires", () => {
    expect(edaDateBound("2017-05-05")).toBe("2017-05-05T00:00:00");
  });

  it("leaves a bound that already carries a time part alone", () => {
    expect(edaDateBound("2017-05-05T00:00:00")).toBe("2017-05-05T00:00:00");
  });

  it("leaves a bound with a zulu suffix alone", () => {
    expect(edaDateBound("2017-05-05T00:00:00Z")).toBe("2017-05-05T00:00:00Z");
  });
});

describe("upsertFilter", () => {
  it("appends a filter for a variable that has none", () => {
    expect(upsertFilter([], FEBRILE)).toEqual([FEBRILE]);
  });

  it("replaces the filter on the same entity and variable rather than adding a second", () => {
    const next = upsertFilter([FEBRILE], { ...FEBRILE, stringSet: ["normal"] });
    expect(next).toHaveLength(1);
    expect(next[0]?.stringSet).toEqual(["normal"]);
  });

  it("keeps a filter on a different variable of the same entity", () => {
    const other = {
      entityId: "ENT_8151325d",
      variableId: "VAR_7033e90f",
      type: "numberRange" as const,
      min: 37,
      max: 42,
    };
    expect(upsertFilter([FEBRILE], other)).toHaveLength(2);
  });
});

describe("removeFilter", () => {
  it("removes by entity and variable", () => {
    expect(removeFilter([FEBRILE], "ENT_8151325d", "VAR_081ab087")).toEqual([]);
  });

  it("leaves the array alone when nothing matches", () => {
    expect(removeFilter([FEBRILE], "ENT_8151325d", "VAR_other")).toEqual([FEBRILE]);
  });
});

describe("isDraftApplicable", () => {
  it("refuses an empty stringSet, which the service rejects with a 400", () => {
    expect(isDraftApplicable({ kind: "stringSet", values: [] })).toBe(false);
  });

  it("accepts a stringSet with one value", () => {
    expect(isDraftApplicable({ kind: "stringSet", values: ["febrile"] })).toBe(true);
  });

  it("refuses a numberRange with a non-numeric bound", () => {
    expect(isDraftApplicable({ kind: "numberRange", min: "", max: "42" })).toBe(false);
  });

  it("accepts a numberRange whose min exceeds its max, which the service answers with count 0", () => {
    expect(isDraftApplicable({ kind: "numberRange", min: "100", max: "0" })).toBe(true);
  });

  it("refuses a dateRange with an empty bound", () => {
    expect(isDraftApplicable({ kind: "dateRange", min: "2017-05-05", max: "" })).toBe(
      false,
    );
  });
});

describe("filterableVariableType", () => {
  it("maps a string variable to stringSet", () => {
    expect(filterableVariableType("string")).toBe("stringSet");
  });

  it("maps integer and number to numberRange", () => {
    expect(filterableVariableType("integer")).toBe("numberRange");
    expect(filterableVariableType("number")).toBe("numberRange");
  });

  it("maps date to dateRange", () => {
    expect(filterableVariableType("date")).toBe("dateRange");
  });

  it("refuses category and longitude", () => {
    expect(filterableVariableType("category")).toBe(null);
    expect(filterableVariableType("longitude")).toBe(null);
  });
});

describe("filterSummary", () => {
  it("summarises a stringSet by its values", () => {
    expect(filterSummary(FEBRILE)).toBe("febrile");
  });

  it("summarises a long stringSet by count", () => {
    expect(filterSummary({ ...FEBRILE, stringSet: ["a", "b", "c", "d"] })).toBe(
      "4 values",
    );
  });

  it("summarises a numberRange as an inclusive interval", () => {
    expect(
      filterSummary({
        entityId: "E",
        variableId: "V",
        type: "numberRange",
        min: 37,
        max: 42,
      }),
    ).toBe("37 to 42");
  });

  it("summarises a dateRange without its time part", () => {
    expect(
      filterSummary({
        entityId: "E",
        variableId: "V",
        type: "dateRange",
        min: "2017-05-05T00:00:00",
        max: "2017-05-11T00:00:00",
      }),
    ).toBe("2017-05-05 to 2017-05-11");
  });

  it("summarises a multiFilter by its operation and sub-filter count", () => {
    expect(
      filterSummary({
        entityId: "E",
        variableId: "V",
        type: "multiFilter",
        operation: "union",
        subFilters: [
          { variableId: "A", stringSet: ["Yes"] },
          { variableId: "B", stringSet: ["Yes"] },
        ],
      }),
    ).toBe("union of 2");
  });
});

describe("collectEntityIds", () => {
  it("returns nothing for an absent tree", () => {
    expect(collectEntityIds(null)).toEqual([]);
  });

  it("returns a single node's id", () => {
    expect(
      collectEntityIds({ id: "ENT_only", displayName: "Only", children: [], variables: [] }),
    ).toEqual(["ENT_only"]);
  });

  it("walks the tree root first", () => {
    expect(
      collectEntityIds({
        id: "ENT_8151325d",
        displayName: "Sample",
        variables: [],
        children: [
          {
            id: "ENT_fd574cd6",
            displayName: "pfal3D7 htseq counts",
            children: [],
            variables: [],
          },
        ],
      }),
    ).toEqual(["ENT_8151325d", "ENT_fd574cd6"]);
  });
});
```

- [ ] **Run and read the failure.**
  `npx vitest run src/features/eda/filterDrafts.test.ts`
  Expected: `Failed to resolve import "./filterDrafts"`.

- [ ] **Implement** `apps/web/src/features/eda/filterDrafts.ts`. Dispatch on
  the filter's `type` discriminant with a `switch` so
  `switch-exhaustiveness-check` catches a missed member; never probe properties.

```ts
import type { EdaEntityNode, EdaFilter, EdaVariableType } from "@pathfinder/shared";

const TIME_PART = /T\d{2}:\d{2}:\d{2}/;

/** The service parses only YYYY-MM-DDTHH:mm:ss; a bare date is a 500. */
export function edaDateBound(value: string): string {
  return TIME_PART.test(value) ? value : `${value}T00:00:00`;
}

export type EdaEditableFilterType = "stringSet" | "numberRange" | "dateRange";

export function filterableVariableType(
  type: EdaVariableType,
): EdaEditableFilterType | null {
  switch (type) {
    case "string":
      return "stringSet";
    case "integer":
    case "number":
      return "numberRange";
    case "date":
      return "dateRange";
    case "longitude":
    case "category":
      return null;
  }
}

export type FilterDraft =
  | { kind: "stringSet"; values: string[] }
  | { kind: "numberRange"; min: string; max: string }
  | { kind: "dateRange"; min: string; max: string };

export function isDraftApplicable(draft: FilterDraft): boolean {
  switch (draft.kind) {
    case "stringSet":
      return draft.values.length > 0;
    case "numberRange":
      return (
        Number.isFinite(Number.parseFloat(draft.min)) &&
        Number.isFinite(Number.parseFloat(draft.max))
      );
    case "dateRange":
      return draft.min !== "" && draft.max !== "";
  }
}

export function draftToFilter(
  entityId: string,
  variableId: string,
  draft: FilterDraft,
): EdaFilter {
  switch (draft.kind) {
    case "stringSet":
      return { entityId, variableId, type: "stringSet", stringSet: draft.values };
    case "numberRange":
      return {
        entityId,
        variableId,
        type: "numberRange",
        min: Number.parseFloat(draft.min),
        max: Number.parseFloat(draft.max),
      };
    case "dateRange":
      return {
        entityId,
        variableId,
        type: "dateRange",
        min: edaDateBound(draft.min),
        max: edaDateBound(draft.max),
      };
  }
}

/** Two filters on one variable compose by AND, so an edit replaces. */
export function upsertFilter(
  filters: readonly EdaFilter[],
  next: EdaFilter,
): EdaFilter[] {
  const without = filters.filter(
    (f) => !(f.entityId === next.entityId && f.variableId === next.variableId),
  );
  return [...without, next];
}

export function removeFilter(
  filters: readonly EdaFilter[],
  entityId: string,
  variableId: string,
): EdaFilter[] {
  return filters.filter(
    (f) => !(f.entityId === entityId && f.variableId === variableId),
  );
}

export function filterSummary(filter: EdaFilter): string {
  switch (filter.type) {
    case "stringSet":
      return filter.stringSet.length > 3
        ? `${filter.stringSet.length} values`
        : filter.stringSet.join(", ");
    case "numberSet":
      return filter.numberSet.length > 3
        ? `${filter.numberSet.length} values`
        : filter.numberSet.join(", ");
    case "dateSet":
      return `${filter.dateSet.length} dates`;
    case "numberRange":
      return `${filter.min} to ${filter.max}`;
    case "dateRange":
      return `${filter.min.slice(0, 10)} to ${filter.max.slice(0, 10)}`;
    case "longitudeRange":
      return `${filter.left} to ${filter.right}`;
    case "multiFilter":
      return `${filter.operation} of ${filter.subFilters.length}`;
  }
}

export function collectEntityIds(root: EdaEntityNode | null): string[] {
  if (root === null) return [];
  return [root.id, ...root.children.flatMap((child) => collectEntityIds(child))];
}
```

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/eda/filterDrafts.test.ts`.

### Task A4: the filter editor

- [ ] **Failing test.** Create
  `apps/web/src/features/eda/cells/FilterEditor.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FilterEditor } from "./FilterEditor";

const SPECIES = {
  id: "VAR_035294d0",
  displayName: "Species",
  type: "string" as const,
  dataShape: "categorical" as const,
  displayType: "default" as const,
  vocabulary: ["P. berghei", "P. falciparum", "P. yoelii"],
  isMultiValued: true,
  hideFrom: [],
};

const TEMPERATURE = {
  id: "VAR_7033e90f",
  displayName: "Temperature",
  type: "integer" as const,
  dataShape: "continuous" as const,
  displayType: "default" as const,
  distributionDefaults: { rangeMin: 37, rangeMax: 42, binWidth: 1 },
  isMultiValued: false,
  hideFrom: [],
};

describe("FilterEditor stringSet", () => {
  it("offers every vocabulary value as a checkbox", () => {
    render(
      <FilterEditor
        entityId="ENT_8151325d"
        variable={SPECIES}
        current={null}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  });

  it("keeps Apply disabled until a value is checked", async () => {
    render(
      <FilterEditor
        entityId="ENT_8151325d"
        variable={SPECIES}
        current={null}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const apply = screen.getByRole("button", { name: "Apply filter" });
    expect(apply).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "P. falciparum" }));
    expect(apply).toBeEnabled();
  });

  it("emits a stringSet filter naming the checked values", async () => {
    const onApply = vi.fn();
    render(
      <FilterEditor
        entityId="ENT_8151325d"
        variable={SPECIES}
        current={null}
        onApply={onApply}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("checkbox", { name: "P. falciparum" }));
    await userEvent.click(screen.getByRole("button", { name: "Apply filter" }));
    expect(onApply).toHaveBeenCalledWith({
      entityId: "ENT_8151325d",
      variableId: "VAR_035294d0",
      type: "stringSet",
      stringSet: ["P. falciparum"],
    });
  });

  it("warns that per-value counts do not partition a multi-valued variable", () => {
    render(
      <FilterEditor
        entityId="ENT_8151325d"
        variable={SPECIES}
        current={null}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByTestId("eda-filter-multivalued-note")).toHaveTextContent(
      "one record can carry several values",
    );
  });

  it("seeds the checkboxes from an existing filter", () => {
    render(
      <FilterEditor
        entityId="ENT_8151325d"
        variable={SPECIES}
        current={{
          entityId: "ENT_8151325d",
          variableId: "VAR_035294d0",
          type: "stringSet",
          stringSet: ["P. yoelii"],
        }}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByRole("checkbox", { name: "P. yoelii" })).toBeChecked();
  });
});

describe("FilterEditor numberRange", () => {
  it("seeds the bounds from the variable range defaults", () => {
    render(
      <FilterEditor
        entityId="ENT_8151325d"
        variable={TEMPERATURE}
        current={null}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Minimum")).toHaveValue(37);
    expect(screen.getByLabelText("Maximum")).toHaveValue(42);
  });

  it("emits numeric bounds, not strings", async () => {
    const onApply = vi.fn();
    render(
      <FilterEditor
        entityId="ENT_8151325d"
        variable={TEMPERATURE}
        current={null}
        onApply={onApply}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Apply filter" }));
    expect(onApply).toHaveBeenCalledWith({
      entityId: "ENT_8151325d",
      variableId: "VAR_7033e90f",
      type: "numberRange",
      min: 37,
      max: 42,
    });
  });
});

describe("FilterEditor dateRange", () => {
  it("appends the time part the service requires", async () => {
    const onApply = vi.fn();
    render(
      <FilterEditor
        entityId="OBI_0000659"
        variable={{
          id: "EUPATH_0043256",
          displayName: "Collection date",
          type: "date",
          dataShape: "continuous",
          displayType: "default",
          distributionDefaults: { rangeMin: "2017-05-05", rangeMax: "2017-05-11" },
          isMultiValued: false,
          hideFrom: [],
        }}
        current={null}
        onApply={onApply}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Apply filter" }));
    expect(onApply).toHaveBeenCalledWith({
      entityId: "OBI_0000659",
      variableId: "EUPATH_0043256",
      type: "dateRange",
      min: "2017-05-05T00:00:00",
      max: "2017-05-11T00:00:00",
    });
  });
});
```

- [ ] **Run and read the failure.** Expected:
  `Failed to resolve import "./FilterEditor"`.

- [ ] **Implement** `apps/web/src/features/eda/cells/FilterEditor.tsx`. It is a
  controlled body with three cases dispatched by
  `filterableVariableType(variable.type)`; it does not own the `Popover`, so it
  is testable in isolation. Seed the draft with `useState(() => ...)` from
  `current` when present, otherwise from `distributionDefaults`. Use
  `Checkbox` and `Input` from `@/components/ui/`. Apply calls
  `onApply(draftToFilter(entityId, variable.id, draft))`.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/eda/cells/FilterEditor.test.tsx`.

### Task A5: the subset cell with live counts

- [ ] **Failing test.** Create
  `apps/web/src/features/eda/cells/SubsetCell.test.tsx`. The study detail
  fixture is the live `STUDY_e973eadd57` tree from
  [../computes-and-jobs.md](../computes-and-jobs.md): sample entity
  `ENT_8151325d` with 12 samples and `VAR_081ab087`
  (`temperature_condition`, vocabulary `["febrile", "normal"]`, 6 each), child
  entity `ENT_fd574cd6` with `VEUPATHDB_GENE_ID` and
  `SEQUENCE_READ_COUNT_SENSE`.

```tsx
/**
 * @vitest-environment jsdom
 */
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

vi.mock("@/lib/components/charts/echartsRegistry", () => ({
  initChart: () => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
  }),
}));

import { useEdaStore } from "@/state/eda";
import { SubsetCell } from "./SubsetCell";

const BASE = "http://localhost:3000";
const server = setupServer();

const STUDY_DETAIL = {
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  displayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
  hasGeneIdVariable: true,
  apps: [],
  rootEntity: {
    id: "ENT_8151325d",
    displayName: "Sample",
    children: [
      {
        id: "ENT_fd574cd6",
        displayName: "pfal3D7 htseq counts",
        children: [],
        variables: [
          {
            id: "VEUPATHDB_GENE_ID",
            displayName: "Gene ID",
            type: "string",
            dataShape: "categorical",
            displayType: "default",
            isMultiValued: false,
            hideFrom: [],
          },
        ],
      },
    ],
    variables: [
      {
        id: "VAR_081ab087",
        displayName: "temperature_condition",
        type: "string",
        dataShape: "categorical",
        displayType: "default",
        vocabulary: ["febrile", "normal"],
        isMultiValued: false,
        hideFrom: [],
      },
      {
        id: "VAR_hidden",
        displayName: "Birth date",
        type: "date",
        dataShape: "continuous",
        displayType: "default",
        isMultiValued: false,
        hideFrom: ["everywhere"],
      },
    ],
  },
};

const COUNTS_UNFILTERED = [
  {
    entityId: "ENT_8151325d",
    entityDisplayName: "Sample",
    count: 12,
    unfilteredCount: 12,
  },
  {
    entityId: "ENT_fd574cd6",
    entityDisplayName: "pfal3D7 htseq counts",
    count: 68640,
    unfilteredCount: 68640,
  },
];

const COUNTS_FEBRILE = [
  {
    entityId: "ENT_8151325d",
    entityDisplayName: "Sample",
    count: 6,
    unfilteredCount: 12,
  },
  {
    entityId: "ENT_fd574cd6",
    entityDisplayName: "pfal3D7 htseq counts",
    count: 34320,
    unfilteredCount: 68640,
  },
];

const FEBRILE_FILTER = {
  entityId: "ENT_8151325d",
  variableId: "VAR_081ab087",
  type: "stringSet",
  stringSet: ["febrile"],
};

function analysis(overrides: Record<string, unknown> = {}) {
  return {
    siteId: "plasmodb",
    datasetId: "DS_e973eadd57",
    studyId: "STUDY_e973eadd57",
    analysisId: "a-1",
    revision: 0,
    studyDisplayName: STUDY_DETAIL.displayName,
    displayName: "Unsaved analysis",
    numFilters: 0,
    numComputations: 0,
    filters: [],
    filterSummaries: [],
    entityCounts: COUNTS_UNFILTERED,
    canExportRows: true,
    ...overrides,
  };
}

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  useEdaStore.getState().reset();
  useEdaStore.getState().applyAnalysisState(analysis());
  server.use(
    http.get(`${BASE}/api/v1/eda/studies/DS_e973eadd57`, () =>
      HttpResponse.json(STUDY_DETAIL),
    ),
  );
});

describe("SubsetCell", () => {
  it("shows the root entity count against its unfiltered total", async () => {
    render(<SubsetCell siteId="plasmodb" conversationId="conv-1" />);
    expect(await screen.findByTestId("eda-entity-ENT_8151325d")).toHaveTextContent(
      "12 of 12",
    );
  });

  it("lists the child entity with its own counts", async () => {
    render(<SubsetCell siteId="plasmodb" conversationId="conv-1" />);
    expect(await screen.findByTestId("eda-entity-ENT_fd574cd6")).toHaveTextContent(
      "68,640 of 68,640",
    );
  });

  it("does not render a variable hidden from everywhere", async () => {
    render(<SubsetCell siteId="plasmodb" conversationId="conv-1" />);
    await screen.findByTestId("eda-entity-ENT_8151325d");
    expect(screen.queryByText("Birth date")).toBe(null);
  });

  it("shows the vocabulary size as a hint on a categorical variable", async () => {
    render(<SubsetCell siteId="plasmodb" conversationId="conv-1" />);
    expect(await screen.findByTestId("eda-variable-VAR_081ab087")).toHaveTextContent(
      "2 values",
    );
  });

  it("counts every entity and patches the analysis when a filter is added", async () => {
    const countBodies: unknown[] = [];
    let patchBody: unknown = null;
    server.use(
      http.post(`${BASE}/api/v1/eda/count`, async ({ request }) => {
        countBodies.push(await request.json());
        return HttpResponse.json({ counts: COUNTS_FEBRILE });
      }),
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({
          analysis: analysis({
            revision: 1,
            numFilters: 1,
            filters: [FEBRILE_FILTER],
            filterSummaries: ["temperature_condition is febrile"],
            entityCounts: COUNTS_FEBRILE,
          }),
          job: null,
          step: null,
        });
      }),
    );

    render(<SubsetCell siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.click(await screen.findByTestId("eda-variable-VAR_081ab087"));
    await userEvent.click(screen.getByRole("checkbox", { name: "febrile" }));
    await userEvent.click(screen.getByRole("button", { name: "Apply filter" }));

    await waitFor(() => {
      expect(useEdaStore.getState().analysis?.revision).toBe(1);
    });
    expect(patchBody).toEqual({
      action: "set-filters",
      filters: [FEBRILE_FILTER],
    });
    expect(countBodies).toHaveLength(1);
    expect(countBodies[0]).toMatchObject({
      siteId: "plasmodb",
      datasetId: "DS_e973eadd57",
      entityIds: ["ENT_8151325d", "ENT_fd574cd6"],
    });
    expect(await screen.findByTestId("eda-entity-ENT_8151325d")).toHaveTextContent(
      "6 of 12",
    );
  });

  it("renders a chip for the filter the server echoed back", async () => {
    useEdaStore.getState().applyAnalysisState(
      analysis({
        revision: 1,
        numFilters: 1,
        filters: [FEBRILE_FILTER],
        filterSummaries: ["temperature_condition is febrile"],
        entityCounts: COUNTS_FEBRILE,
      }),
    );
    render(<SubsetCell siteId="plasmodb" conversationId="conv-1" />);
    const chip = await screen.findByTestId(
      "eda-filter-chip-ENT_8151325d-VAR_081ab087",
    );
    expect(chip).toHaveTextContent("temperature_condition");
    expect(chip).toHaveTextContent("febrile");
  });

  it("reports a filter it cannot parse rather than hiding it", async () => {
    useEdaStore.getState().applyAnalysisState(
      analysis({
        revision: 1,
        numFilters: 2,
        filters: [FEBRILE_FILTER, { type: "somethingNew", entityId: "E" }],
      }),
    );
    render(<SubsetCell siteId="plasmodb" conversationId="conv-1" />);
    expect(
      await screen.findByTestId("eda-subset-unparsed-filters"),
    ).toHaveTextContent("1 filter on this analysis cannot be edited here");
  });

  it("says the count is unavailable and rolls the optimistic edit back on failure", async () => {
    server.use(
      http.post(`${BASE}/api/v1/eda/count`, () =>
        HttpResponse.json({ detail: "count failed" }, { status: 500 }),
      ),
    );
    render(<SubsetCell siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.click(await screen.findByTestId("eda-variable-VAR_081ab087"));
    await userEvent.click(screen.getByRole("checkbox", { name: "febrile" }));
    await userEvent.click(screen.getByRole("button", { name: "Apply filter" }));
    expect(await screen.findByTestId("eda-subset-count-error")).toHaveTextContent(
      "count failed",
    );
    await waitFor(() => {
      expect(useEdaStore.getState().localFilters).toBe(null);
    });
  });

  it("draws a bar chart for a categorical variable and reports the value coverage", async () => {
    server.use(
      http.post(`${BASE}/api/v1/eda/distribution`, () =>
        HttpResponse.json({
          variableId: "VAR_081ab087",
          variableDisplayName: "temperature_condition",
          labels: ["febrile", "normal"],
          values: [6, 6],
          subsetSize: 12,
          numVarValues: 12,
          numMissingCases: 0,
          isMultiValued: false,
        }),
      ),
    );
    render(<SubsetCell siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.click(await screen.findByTestId("eda-variable-VAR_081ab087"));
    expect(await screen.findByTestId("eda-subset-sparkline-bar")).toHaveAttribute(
      "role",
      "img",
    );
    expect(screen.queryByTestId("eda-subset-sparkline-histogram")).toBe(null);
    expect(screen.getByTestId("eda-subset-coverage")).toHaveTextContent(
      "12 of 12 records have a value",
    );
  });
});
```

- [ ] **Run and read the failure.** Expected:
  `Failed to resolve import "./SubsetCell"`.

- [ ] **Implement.** Split across `SubsetCell.tsx`, `EntityTree.tsx`,
  `VariableRow.tsx`, `FilterChip.tsx` and `DistributionSparkline.tsx` to stay
  under `max-lines`. `SubsetCell` owns the data flow:

```tsx
"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import type { EdaEntityCount, EdaFilter } from "@pathfinder/shared";

import { toUserMessage } from "@/lib/api/errors";
import {
  countEdaSubset,
  edaStudyDetailOptions,
  patchConversationEda,
} from "@/lib/api/eda";
import { selectEffectiveFilters, useEdaStore } from "@/state/eda";

import { CellShell } from "./CellShell";
import { collectEntityIds } from "../filterDrafts";

export function SubsetCell({
  siteId,
  conversationId,
}: {
  siteId: string;
  conversationId: string;
}) {
  const binding = useEdaStore((s) => s.binding);
  const analysis = useEdaStore((s) => s.analysis);
  const filters = useEdaStore(selectEffectiveFilters);
  const setLocalFilters = useEdaStore((s) => s.setLocalFilters);
  const applyAnalysisState = useEdaStore((s) => s.applyAnalysisState);

  const [liveCounts, setLiveCounts] = useState<EdaEntityCount[] | null>(null);
  const [countError, setCountError] = useState<string | null>(null);

  const detail = useQuery({
    ...edaStudyDetailOptions(siteId, binding?.datasetId ?? ""),
    enabled: binding !== null,
  });

  const edit = useMutation({
    mutationFn: async (next: EdaFilter[]) => {
      const entityIds = collectEntityIds(detail.data?.rootEntity ?? null);
      const counted = await countEdaSubset({
        siteId,
        datasetId: binding?.datasetId ?? "",
        entityIds,
        filters: next,
      });
      const patched = await patchConversationEda(conversationId, {
        action: "set-filters",
        filters: next,
      });
      return { counted, patched };
    },
    onMutate: (next) => {
      setCountError(null);
      setLocalFilters(next);
    },
    onSuccess: ({ counted, patched }) => {
      setLiveCounts(counted.counts);
      if (patched.analysis !== null) applyAnalysisState(patched.analysis);
    },
    onError: (error) => {
      setLocalFilters(null);
      setCountError(toUserMessage(error, "Subset count failed"));
      toast.error(toUserMessage(error, "Subset count failed"));
    },
  });

  const counts = liveCounts ?? analysis?.entityCounts ?? [];
  // ... render CellShell with EntityTree, the chips, the unparsed notice and
  // DistributionSparkline
}
```

`DistributionSparkline` fetches through `edaDistribution` in its own `useQuery`
keyed by the selected variable and the effective filters, and picks
`HistogramChart` or `BarChart` from the variable's `dataShape` per the UX
specification. Give the two charts the distinct testids
`eda-subset-sparkline-histogram` and `eda-subset-sparkline-bar` so a test can
prove which form was chosen.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/eda/cells/SubsetCell.test.tsx src/features/eda/filterDrafts.test.ts`.

### Task A6: the workbench shell, the route, and unbinding

- [ ] **Failing test.** Create
  `apps/web/src/features/eda/EdaWorkbench.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { useEdaStore } from "@/state/eda";
import { EdaWorkbench } from "./EdaWorkbench";

const BASE = "http://localhost:3000";
const server = setupServer();

const ANALYSIS = {
  siteId: "plasmodb",
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  analysisId: "a-1",
  revision: 0,
  studyDisplayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
  displayName: "Febrile samples",
  numFilters: 0,
  numComputations: 0,
  filters: [],
  filterSummaries: [],
  entityCounts: [],
  canExportRows: true,
};

beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => useEdaStore.getState().reset());

describe("EdaWorkbench", () => {
  it("shows the study picker and no cells when nothing is bound", async () => {
    server.use(
      http.get(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({ analysis: null }),
      ),
    );
    render(<EdaWorkbench siteId="plasmodb" conversationId="conv-1" />);
    expect(await screen.findByTestId("eda-study-picker")).toBeInTheDocument();
    expect(screen.queryByTestId("eda-subset-cell")).toBe(null);
    expect(screen.getByTestId("eda-workbench-header")).toHaveTextContent(
      "No study selected",
    );
  });

  it("hydrates from the binding endpoint and mounts the three cells", async () => {
    server.use(
      http.get(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({ analysis: ANALYSIS }),
      ),
    );
    render(<EdaWorkbench siteId="plasmodb" conversationId="conv-1" />);
    expect(await screen.findByTestId("eda-subset-cell")).toBeInTheDocument();
    expect(screen.getByTestId("eda-compute-cell")).toBeInTheDocument();
    expect(screen.getByTestId("eda-viz-cell")).toBeInTheDocument();
  });

  it("names the study and the analysis separately in the header", async () => {
    server.use(
      http.get(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({ analysis: ANALYSIS }),
      ),
    );
    render(<EdaWorkbench siteId="plasmodb" conversationId="conv-1" />);
    const header = await screen.findByTestId("eda-workbench-header");
    expect(header).toHaveTextContent(
      "Heat shock response in sensitive mutants (LRR5, DHC)",
    );
    expect(header).toHaveTextContent("Febrile samples");
  });

  it("unbinds upstream before it clears the store", async () => {
    let patchBody: unknown = null;
    server.use(
      http.get(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({ analysis: ANALYSIS }),
      ),
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ analysis: null, job: null, step: null });
      }),
    );
    render(<EdaWorkbench siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Change study" }),
    );
    await waitFor(() => {
      expect(useEdaStore.getState().binding).toBe(null);
    });
    expect(patchBody).toEqual({ action: "unbind" });
  });

  it("keeps the binding when unbinding fails, so the tab matches the server", async () => {
    server.use(
      http.get(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({ analysis: ANALYSIS }),
      ),
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({ detail: "unbind failed" }, { status: 500 }),
      ),
    );
    render(<EdaWorkbench siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Change study" }),
    );
    await waitFor(() => {
      expect(screen.getByTestId("eda-subset-cell")).toBeInTheDocument();
    });
    expect(useEdaStore.getState().binding?.analysisId).toBe("a-1");
  });

  it("reports a failed binding read rather than showing the picker", async () => {
    server.use(
      http.get(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({ detail: "binding read failed" }, { status: 500 }),
      ),
    );
    render(<EdaWorkbench siteId="plasmodb" conversationId="conv-1" />);
    expect(await screen.findByTestId("eda-binding-error")).toHaveTextContent(
      "binding read failed",
    );
  });
});
```

- [ ] **Run and read the failure.** Expected:
  `Failed to resolve import "./EdaWorkbench"`.

- [ ] **Implement** `EdaWorkbench.tsx` and `CellShell.tsx`. Hydration from the
  binding endpoint uses a plain `useQuery` plus the render-time guard, not an
  effect:

```tsx
const bindingQuery = useQuery(conversationEdaOptions(conversationId));
const applyAnalysisState = useEdaStore((s) => s.applyAnalysisState);
const [hydrated, setHydrated] = useState<unknown>(null);
const fetchedAnalysis = bindingQuery.data?.analysis ?? null;
if (fetchedAnalysis !== null && hydrated !== fetchedAnalysis) {
  setHydrated(fetchedAnalysis);
  queueMicrotask(() => applyAnalysisState(fetchedAnalysis));
}
```

and unbinding is a mutation that resets the store only on success:

```tsx
const unbind = useMutation({
  mutationFn: () => patchConversationEda(conversationId, { action: "unbind" }),
  onSuccess: () => {
    useEdaStore.getState().reset();
    setHydrated(null);
  },
  onError: (error) =>
    toast.error(toUserMessage(error, "Could not close the analysis")),
});
```

`setHydrated(null)` matters: without it the render-time guard still holds the
old analysis object and would re-hydrate the binding it just dropped.

- [ ] **Implement the route**
  `apps/web/src/app/[siteId]/(app)/conversation/[conversationId]/eda/page.tsx`,
  a copy of the strategy route's shape:

```tsx
"use client";

import { use } from "react";

import { EdaWorkbench } from "@/features/eda/EdaWorkbench";

export default function EdaRoute({
  params,
}: {
  params: Promise<{ siteId: string; conversationId: string }>;
}) {
  const { siteId, conversationId } = use(params);
  return <EdaWorkbench siteId={siteId} conversationId={conversationId} />;
}
```

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/eda/EdaWorkbench.test.tsx`.

### Section A close-out

- [ ] `cd apps/web && yarn format`
- [ ] `npx tsc --noEmit && npx eslint src/ && node scripts/check-boundaries.mjs && node scripts/check-weak-assertions.mjs && npx vitest run`
- [ ] Report: every named state from the table with the file and testid that
  implements it, and any table row with no implementation; every file over 200
  lines with its count; zero-debt statement or the debt.

## Implementer B: compute cell, viz cell, step export

### Files

**Create**

- `apps/web/src/features/eda/cells/ComputeCell.tsx`
- `apps/web/src/features/eda/cells/ComputeConfigForm.tsx`
- `apps/web/src/features/eda/cells/ComputeProgress.tsx`
- `apps/web/src/features/eda/cells/VizCell.tsx`
- `apps/web/src/features/eda/cells/VolcanoControls.tsx`
- `apps/web/src/features/eda/ExportStepButton.tsx`
- `apps/web/src/features/eda/computeConfig.ts`

**Test**

- `apps/web/src/features/eda/computeConfig.test.ts`
- `apps/web/src/features/eda/cells/ComputeCell.test.tsx`
- `apps/web/src/features/eda/cells/VizCell.test.tsx`
- `apps/web/src/features/eda/ExportStepButton.test.tsx`

### Interfaces

**Consumes** from batch 5 and from Implementer A:

```ts
import { CellShell } from "./CellShell";
import { VolcanoChart } from "@/lib/components/charts/VolcanoChart";
import { ScatterChart } from "@/lib/components/charts/ScatterChart";
import { selectVolcanoGenes } from "@/lib/eda/volcanoSelection";
import { edaViz, patchConversationEda } from "@/lib/api/eda";
import { strategyQueryKey, toStrategy } from "@/lib/api/strategy";
import { isEdaJobComplete, isEdaJobFailed, isEdaJobRunning, useEdaStore } from "@/state/eda";
```

`strategyQueryKey` and `toStrategy` come from `@/lib/api/strategy.ts` lines
9-21 and are the whole reason `features/eda` needs no import from
`features/strategy`.

**Produces:** `ComputeCell`, `VizCell`, `ExportStepButton`, all mounted by
`EdaWorkbench`, plus `buildDifferentialExpressionConfig` in `computeConfig.ts`.

### The compute path, and how progress arrives

The tab does not talk to `/eda/computes` directly. It sends

```
PATCH /api/v1/conversations/{id}/eda
{ "action": "run-compute", "computation": EdaComputationSpec }
```

and the response carries
`job: { jobId, taskId, appName, status }`. Two settled facts decide the whole
design:

- **`taskId` is null for a tab-started compute.** There is no
  `background_tasks` row, so `taskStatusOptions` from `lib/api/tasks.ts` is not
  available and must not be used. It stays the chat-side mechanism.
- **`run-compute` is an idempotent submit-or-poll.** The job id is the MD5 of
  the request ([../computes-and-jobs.md](../computes-and-jobs.md)), so the same
  configuration always addresses the same job and **repeating the identical
  action is the status poll.**

So `ComputeProgress` polls by re-issuing the same mutation payload through a
`useQuery` whose `queryFn` calls `patchConversationEda` with the identical
`run-compute` body and whose `refetchInterval` returns `2_000` while the job is
running and `false` otherwise. It mirrors each answer into the store with
`applyJob`, so `VizCell`, `ExportStepButton` and batch 7's cards all read one
job state. There is no percentage on the wire, so the bar is indeterminate and
the cell shows the status word.

**The six job states**, from [../computes-and-jobs.md](../computes-and-jobs.md):
`no-such-job`, `queued`, `in-progress`, `complete`, `failed`, `expired`. Only
`complete` enables the visualization: the viz endpoint answered a
never-computed job with
`400 {"status":"bad-request","message":"Compute results are not available for the requested job."}`.
An `expired` job is re-runnable by submitting again; a `failed` job is not. The
whole run took under 35 seconds live for 12 samples and 5720 genes, so no
long-wait affordance is needed beyond the status line. Use
`isEdaJobRunning`, `isEdaJobComplete` and `isEdaJobFailed` from `@/state/eda`
rather than comparing strings at each call site.

### Task B1: the differential expression config is built from live metadata

Every rule here is live-verified in
[../computes-and-jobs.md](../computes-and-jobs.md): the wire method values are
exactly `DESeq` and `limma` (`DESeq2` is **not** valid; the frontend shows
`DESeq2` as the display name for the key `DESeq`); `identifierVariable` and
`valueVariable` must be on the **same entity** or the plugin throws;
`comparator.variable` is read from an ancestor entity; `groupA` and `groupB` are
`LabeledRange[]` and a label-only member such as `{"label": "normal"}` is
accepted; `pValueFloor` defaults to `"1e-200"` and is a **string**; there is no
`collectionVariable` and no `dataFormat` on this compute; an out-of-vocabulary
group label is accepted at submit and only surfaces later as a `failed` job.

- [ ] **Failing test.** Create
  `apps/web/src/features/eda/computeConfig.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  buildDifferentialExpressionConfig,
  DifferentialExpressionConfigError,
  isComputeConfigComplete,
} from "./computeConfig";

const draft = {
  identifierEntityId: "ENT_fd574cd6",
  identifierVariableId: "VEUPATHDB_GENE_ID",
  valueVariableId: "SEQUENCE_READ_COUNT_SENSE",
  comparatorEntityId: "ENT_8151325d",
  comparatorVariableId: "VAR_081ab087",
  groupA: ["normal"],
  groupB: ["febrile"],
  method: "DESeq" as const,
};

describe("buildDifferentialExpressionConfig", () => {
  it("builds the recorded live request config", () => {
    expect(buildDifferentialExpressionConfig(draft)).toEqual({
      identifierVariable: {
        entityId: "ENT_fd574cd6",
        variableId: "VEUPATHDB_GENE_ID",
      },
      valueVariable: {
        entityId: "ENT_fd574cd6",
        variableId: "SEQUENCE_READ_COUNT_SENSE",
      },
      comparator: {
        variable: { entityId: "ENT_8151325d", variableId: "VAR_081ab087" },
        groupA: [{ label: "normal" }],
        groupB: [{ label: "febrile" }],
      },
      differentialExpressionMethod: "DESeq",
      pValueFloor: "1e-200",
    });
  });

  it("puts the value variable on the identifier variable's entity", () => {
    const config = buildDifferentialExpressionConfig(draft);
    expect(config.valueVariable.entityId).toBe(config.identifierVariable.entityId);
  });

  it("accepts limma as the other wire method", () => {
    expect(
      buildDifferentialExpressionConfig({ ...draft, method: "limma" })
        .differentialExpressionMethod,
    ).toBe("limma");
  });

  it("keeps the p-value floor a string", () => {
    expect(buildDifferentialExpressionConfig(draft).pValueFloor).toBe("1e-200");
  });

  it("throws when a group shares a label with the other group", () => {
    expect(() =>
      buildDifferentialExpressionConfig({ ...draft, groupB: ["normal"] }),
    ).toThrow(DifferentialExpressionConfigError);
  });

  it("throws when a group is empty", () => {
    expect(() => buildDifferentialExpressionConfig({ ...draft, groupB: [] })).toThrow(
      DifferentialExpressionConfigError,
    );
  });
});

describe("isComputeConfigComplete", () => {
  it("is true for the recorded draft", () => {
    expect(isComputeConfigComplete(draft)).toBe(true);
  });

  it("is false while no comparator variable is chosen", () => {
    expect(isComputeConfigComplete({ ...draft, comparatorVariableId: "" })).toBe(false);
  });

  it("is false while either group is empty", () => {
    expect(isComputeConfigComplete({ ...draft, groupA: [] })).toBe(false);
  });

  it("is false while the two groups share a label", () => {
    expect(isComputeConfigComplete({ ...draft, groupB: ["normal"] })).toBe(false);
  });
});
```

- [ ] **Run and read the failure.** Expected:
  `Failed to resolve import "./computeConfig"`.

- [ ] **Implement** `apps/web/src/features/eda/computeConfig.ts` with a named
  `DifferentialExpressionConfigError extends Error` whose message names which
  rule failed, and `P_VALUE_FLOOR = "1e-200"` as a module constant.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/eda/computeConfig.test.ts`.

### Task B2: the compute cell

**Native `<select>`, not the Radix `Select`.** The comparator variable, the two
group pickers and the method picker are native `<select>` elements styled with
Tailwind, the way `features/workbench/components/ParamNameSelect.tsx` does it.
Two reasons, both practical: Playwright drives a native select with
`locator.selectOption(value)` in one call, and jsdom has no pointer capture for
the Radix listbox. The method picker's option labels are `DESeq2` and `limma`
and its values are `DESeq` and `limma`.

- [ ] **Failing test.** Create
  `apps/web/src/features/eda/cells/ComputeCell.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { useEdaStore } from "@/state/eda";
import { ComputeCell } from "./ComputeCell";

const BASE = "http://localhost:3000";
const server = setupServer();
const JOB_ID = "db04204e5386396e1ca2cb78469ab6fb";

const STUDY_DETAIL = {
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  displayName: "Heat shock response",
  hasGeneIdVariable: true,
  apps: [
    {
      name: "differentialexpression",
      displayName: "Differential expression",
      projects: ["PlasmoDB"],
    },
  ],
  rootEntity: {
    id: "ENT_8151325d",
    displayName: "Sample",
    variables: [
      {
        id: "VAR_081ab087",
        displayName: "temperature_condition",
        type: "string",
        dataShape: "categorical",
        displayType: "default",
        vocabulary: ["febrile", "normal"],
        isMultiValued: false,
        hideFrom: [],
      },
    ],
    children: [
      {
        id: "ENT_fd574cd6",
        displayName: "pfal3D7 htseq counts",
        children: [],
        variables: [
          {
            id: "VEUPATHDB_GENE_ID",
            displayName: "Gene ID",
            type: "string",
            dataShape: "categorical",
            displayType: "default",
            isMultiValued: false,
            hideFrom: [],
          },
          {
            id: "SEQUENCE_READ_COUNT_SENSE",
            displayName: "Read count, sense",
            type: "integer",
            dataShape: "continuous",
            displayType: "default",
            isMultiValued: false,
            hideFrom: [],
          },
        ],
      },
    ],
  },
};

const ANALYSIS = {
  siteId: "plasmodb",
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  analysisId: "a-1",
  revision: 0,
  studyDisplayName: "Heat shock response",
  displayName: "Unsaved analysis",
  numFilters: 0,
  numComputations: 0,
  filters: [],
  filterSummaries: [],
  entityCounts: [],
  canExportRows: true,
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  useEdaStore.getState().reset();
  useEdaStore.getState().applyAnalysisState(ANALYSIS);
  server.use(
    http.get(`${BASE}/api/v1/eda/studies/DS_e973eadd57`, () =>
      HttpResponse.json(STUDY_DETAIL),
    ),
  );
});

async function fillConfig() {
  await userEvent.selectOptions(
    await screen.findByLabelText("Comparator variable"),
    "VAR_081ab087",
  );
  await userEvent.selectOptions(screen.getByLabelText("Group A"), "normal");
  await userEvent.selectOptions(screen.getByLabelText("Group B"), "febrile");
}

describe("ComputeCell", () => {
  it("offers the study's apps and defaults to differential expression", async () => {
    render(<ComputeCell siteId="plasmodb" conversationId="conv-1" />);
    expect(await screen.findByLabelText("Analysis")).toHaveValue(
      "differentialexpression",
    );
  });

  it("offers DESeq2 as a label over the DESeq wire value", async () => {
    render(<ComputeCell siteId="plasmodb" conversationId="conv-1" />);
    expect(await screen.findByLabelText("Method")).toHaveValue("DESeq");
    expect(
      screen.getByRole("option", { name: "DESeq2" }),
    ).toHaveAttribute("value", "DESeq");
  });

  it("keeps Run disabled until both groups are chosen", async () => {
    render(<ComputeCell siteId="plasmodb" conversationId="conv-1" />);
    const run = await screen.findByRole("button", { name: "Run compute" });
    expect(run).toBeDisabled();
    await fillConfig();
    expect(run).toBeEnabled();
  });

  it("sends the run-compute action with the recorded config", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({
          analysis: ANALYSIS,
          job: {
            jobId: JOB_ID,
            taskId: null,
            appName: "differentialexpression",
            status: "complete",
          },
          step: null,
        });
      }),
    );
    render(<ComputeCell siteId="plasmodb" conversationId="conv-1" />);
    await fillConfig();
    await userEvent.click(screen.getByRole("button", { name: "Run compute" }));

    await waitFor(() => {
      expect(bodies[0]).toEqual({
        action: "run-compute",
        computation: {
          type: "differentialexpression",
          config: {
            identifierVariable: {
              entityId: "ENT_fd574cd6",
              variableId: "VEUPATHDB_GENE_ID",
            },
            valueVariable: {
              entityId: "ENT_fd574cd6",
              variableId: "SEQUENCE_READ_COUNT_SENSE",
            },
            comparator: {
              variable: { entityId: "ENT_8151325d", variableId: "VAR_081ab087" },
              groupA: [{ label: "normal" }],
              groupB: [{ label: "febrile" }],
            },
            differentialExpressionMethod: "DESeq",
            pValueFloor: "1e-200",
          },
        },
      });
    });
  });

  it("mirrors the job into the store and shows its status", async () => {
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({
          analysis: ANALYSIS,
          job: {
            jobId: JOB_ID,
            taskId: null,
            appName: "differentialexpression",
            status: "in-progress",
          },
          step: null,
        }),
      ),
    );
    render(<ComputeCell siteId="plasmodb" conversationId="conv-1" />);
    await fillConfig();
    await userEvent.click(screen.getByRole("button", { name: "Run compute" }));
    expect(await screen.findByTestId("eda-compute-progress")).toHaveTextContent(
      "in-progress",
    );
    await waitFor(() => {
      expect(useEdaStore.getState().jobs[JOB_ID]?.appName).toBe(
        "differentialexpression",
      );
    });
  });

  it("polls by repeating the identical run-compute action", async () => {
    const bodies: unknown[] = [];
    let call = 0;
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, async ({ request }) => {
        bodies.push(await request.json());
        call += 1;
        return HttpResponse.json({
          analysis: ANALYSIS,
          job: {
            jobId: JOB_ID,
            taskId: null,
            appName: "differentialexpression",
            status: call === 1 ? "queued" : "complete",
          },
          step: null,
        });
      }),
    );
    render(<ComputeCell siteId="plasmodb" conversationId="conv-1" />);
    await fillConfig();
    await userEvent.click(screen.getByRole("button", { name: "Run compute" }));
    await waitFor(
      () => {
        expect(useEdaStore.getState().jobs[JOB_ID]?.status).toBe("complete");
      },
      { timeout: 10_000 },
    );
    expect(bodies.length).toBeGreaterThan(1);
    expect(bodies[1]).toEqual(bodies[0]);
  });

  it("stops polling once the job is complete", async () => {
    let call = 0;
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, () => {
        call += 1;
        return HttpResponse.json({
          analysis: ANALYSIS,
          job: {
            jobId: JOB_ID,
            taskId: null,
            appName: "differentialexpression",
            status: "complete",
          },
          step: null,
        });
      }),
    );
    render(<ComputeCell siteId="plasmodb" conversationId="conv-1" />);
    await fillConfig();
    await userEvent.click(screen.getByRole("button", { name: "Run compute" }));
    await waitFor(() => {
      expect(useEdaStore.getState().jobs[JOB_ID]?.status).toBe("complete");
    });
    const settled = call;
    await new Promise((resolve) => setTimeout(resolve, 3_000));
    expect(call).toBe(settled);
  });

  it("says a failed job cannot be re-run and offers a re-run for an expired one", async () => {
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({
          analysis: ANALYSIS,
          job: {
            jobId: JOB_ID,
            taskId: null,
            appName: "differentialexpression",
            status: "failed",
          },
          step: null,
        }),
      ),
    );
    render(<ComputeCell siteId="plasmodb" conversationId="conv-1" />);
    await fillConfig();
    await userEvent.click(screen.getByRole("button", { name: "Run compute" }));
    expect(await screen.findByTestId("eda-compute-failed")).toHaveTextContent(
      "This compute failed",
    );
  });

  it("refuses to submit two groups that share a label", async () => {
    render(<ComputeCell siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.selectOptions(
      await screen.findByLabelText("Comparator variable"),
      "VAR_081ab087",
    );
    await userEvent.selectOptions(screen.getByLabelText("Group A"), "normal");
    await userEvent.selectOptions(screen.getByLabelText("Group B"), "normal");
    expect(screen.getByTestId("eda-compute-config-error")).toHaveTextContent(
      "the same label",
    );
    expect(screen.getByRole("button", { name: "Run compute" })).toBeDisabled();
  });
});
```

The polling tests use real timers against a 2000 ms interval, so give them the
explicit timeouts shown. Do not shorten the production interval to make a test
faster: that is a test-driven production change.

- [ ] **Run and read the failure.** Expected:
  `Failed to resolve import "./ComputeCell"`.

- [ ] **Implement** `ComputeCell.tsx`, `ComputeConfigForm.tsx` and
  `ComputeProgress.tsx`. The identifier and value variables are derived, not
  chosen: the identifier is the single `VEUPATHDB_GENE_ID` variable in the tree
  and the value variable list is the `integer` and `number` variables on that
  same entity. If the tree carries no `VEUPATHDB_GENE_ID`, the cell renders the
  named notice `ComputeGeneEntityMissingNotice` and no form: a study needs
  exactly one such variable to export genes ([overview.md](overview.md), wire
  truths).

`ComputeProgress` receives the submitted `EdaComputationSpec` and polls with it:

```tsx
const poll = useQuery({
  queryKey: ["eda", "compute", conversationId, computation] as const,
  queryFn: async () => {
    const response = await patchConversationEda(conversationId, {
      action: "run-compute",
      computation,
    });
    if (response.job !== null) useEdaStore.getState().applyJob(response.job);
    return response.job;
  },
  refetchInterval: (query) => {
    const job = query.state.data ?? null;
    if (job === null) return 2_000;
    return isEdaJobRunning(job) ? 2_000 : false;
  },
});
```

The `queryFn` re-submits the identical action, which the settled contract
defines as the status poll. There is no separate poll endpoint and no task row.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/eda/cells/ComputeCell.test.tsx`.

### Task B3: the viz cell

The volcano's thresholds are **never sent to the service**: the upstream
volcanoplot `config` is an object with no properties allowed and the plugin
pipes the compute's statistics file straight through
([../visualizations.md](../visualizations.md)). So a threshold change re-renders
and does not refetch. That is the single most important behavior in this task,
and it gets its own test with a request counter.

The settled part gives `chart` five values and a point cloud. `volcano` and
`scatter` are renderable from a point cloud; `histogram`, `bar` and `boxplot`
are not, and the cell says so rather than drawing a wrong chart.

- [ ] **Failing test.** Create
  `apps/web/src/features/eda/cells/VizCell.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

vi.mock("@/lib/components/charts/echartsRegistry", () => ({
  initChart: () => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
  }),
}));

import { useEdaStore } from "@/state/eda";
import { VizCell } from "./VizCell";

const BASE = "http://localhost:3000";
const server = setupServer();

const ANALYSIS = {
  siteId: "plasmodb",
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  analysisId: "a-1",
  revision: 0,
  studyDisplayName: "Heat shock response",
  displayName: "Unsaved analysis",
  numFilters: 0,
  numComputations: 1,
  filters: [],
  filterSummaries: [],
  entityCounts: [],
  canExportRows: true,
};

const VOLCANO = {
  datasetId: "DS_e973eadd57",
  analysisId: "a-1",
  chart: "volcano" as const,
  effectSizeLabel: "log2(Fold Change)",
  effectSizeThreshold: 1,
  significanceThreshold: 0.05,
  effectDirection: "upAndDown" as const,
  totalPoints: 4,
  retainedPoints: 2,
  points: [
    {
      pointId: "PF3D7_0100100",
      effectSize: -0.218035922112735,
      pValue: 0.350285751849808,
      adjustedPValue: 0.46960449943855,
      retained: false,
    },
    {
      pointId: "PF3D7_0100200",
      effectSize: 3.94437533216012,
      pValue: 1.95781599815607e-5,
      adjustedPValue: 0.000137772236907279,
      retained: true,
    },
    {
      pointId: "PF3D7_0100300",
      effectSize: -2.5,
      pValue: 0.001,
      adjustedPValue: 0.004,
      retained: true,
    },
    { pointId: "PF3D7_MIT04200", effectSize: -1.49447459261845, retained: false },
  ],
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => {
  useEdaStore.getState().reset();
  useEdaStore.getState().applyAnalysisState(ANALYSIS);
});

describe("VizCell", () => {
  it("says why there is nothing to plot before a compute completes", () => {
    render(<VizCell siteId="plasmodb" conversationId="conv-1" />);
    expect(screen.getByTestId("eda-viz-unavailable")).toHaveTextContent(
      "Run a compute to see its plots.",
    );
  });

  it("renders the volcano from a viz payload in the store", () => {
    useEdaStore.getState().applyViz(VOLCANO);
    render(<VizCell siteId="plasmodb" conversationId="conv-1" />);
    expect(screen.getByTestId("eda-viz-volcano")).toHaveAttribute("role", "img");
  });

  it("counts the selected genes and agrees with the retained total", () => {
    useEdaStore.getState().applyViz(VOLCANO);
    render(<VizCell siteId="plasmodb" conversationId="conv-1" />);
    expect(screen.getByTestId("eda-volcano-selection")).toHaveTextContent(
      "2 genes selected",
    );
    expect(screen.getByTestId("eda-volcano-selection")).toHaveTextContent(
      "2 of 4 retained by the compute",
    );
  });

  it("re-counts on a threshold change without asking the server for anything", async () => {
    useEdaStore.getState().applyViz(VOLCANO);
    let vizCalls = 0;
    server.use(
      http.post(`${BASE}/api/v1/eda/viz`, () => {
        vizCalls += 1;
        return HttpResponse.json(VOLCANO);
      }),
    );
    render(<VizCell siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.clear(screen.getByLabelText("Effect size threshold"));
    await userEvent.type(screen.getByLabelText("Effect size threshold"), "3");
    await waitFor(() => {
      expect(screen.getByTestId("eda-volcano-selection")).toHaveTextContent(
        "1 gene selected",
      );
    });
    expect(vizCalls).toBe(0);
  });

  it("writes the threshold edit into the store so export and chat agree", async () => {
    useEdaStore.getState().applyViz(VOLCANO);
    render(<VizCell siteId="plasmodb" conversationId="conv-1" />);
    await userEvent.selectOptions(screen.getByLabelText("Direction"), "upOnly");
    await waitFor(() => {
      expect(useEdaStore.getState().volcanoThresholds.direction).toBe("upOnly");
    });
  });

  it("reports the point it could not plot", () => {
    useEdaStore.getState().applyViz(VOLCANO);
    render(<VizCell siteId="plasmodb" conversationId="conv-1" />);
    expect(screen.getByTestId("eda-viz-volcano-dropped")).toHaveTextContent(
      "1 point without a p-value was not plotted",
    );
  });

  it("draws a scatter for chart scatter, with no threshold controls", () => {
    useEdaStore.getState().applyViz({ ...VOLCANO, chart: "scatter" });
    render(<VizCell siteId="plasmodb" conversationId="conv-1" />);
    expect(screen.getByTestId("eda-viz-scatter")).toHaveAttribute("role", "img");
    expect(screen.queryByLabelText("Effect size threshold")).toBe(null);
  });

  it("says a bar chart cannot be drawn from a point cloud", () => {
    useEdaStore.getState().applyViz({ ...VOLCANO, chart: "bar" });
    render(<VizCell siteId="plasmodb" conversationId="conv-1" />);
    expect(screen.getByTestId("eda-viz-unsupported-chart")).toHaveTextContent(
      "bar plots are not available from this compute",
    );
  });

  it("says the same for a histogram and a boxplot", () => {
    useEdaStore.getState().applyViz({ ...VOLCANO, chart: "histogram" });
    render(<VizCell siteId="plasmodb" conversationId="conv-1" />);
    expect(screen.getByTestId("eda-viz-unsupported-chart")).toHaveTextContent(
      "histogram plots are not available from this compute",
    );
    useEdaStore.getState().applyViz({ ...VOLCANO, chart: "boxplot" });
    expect(screen.getByTestId("eda-viz-unsupported-chart")).toHaveTextContent(
      "boxplot plots are not available from this compute",
    );
  });
});
```

The counts are hand-computed at `effectSizeThreshold: 1`,
`significanceThreshold: 0.05`, `adjustedPValue`: `PF3D7_0100200` up,
`PF3D7_0100300` down, `PF3D7_0100100` below the effect gate,
`PF3D7_MIT04200` dropped for having no p-value. Raising the effect threshold to
3 leaves only `PF3D7_0100200`. The store adopts the payload's own thresholds on
the first `applyViz`, which is why the default render already agrees with
`retainedPoints`.

- [ ] **Run and read the failure.** Expected:
  `Failed to resolve import "./VizCell"`.

- [ ] **Implement** `VizCell.tsx` and `VolcanoControls.tsx`. `VizCell` reads
  `useEdaStore((s) => s.viz)` and dispatches on `chart` with a `switch`, so a
  sixth value would fail compilation:

```tsx
switch (viz.chart) {
  case "volcano":
    return <VolcanoPanel payload={viz} />;
  case "scatter":
    return <ScatterPanel payload={viz} />;
  case "histogram":
  case "bar":
  case "boxplot":
    return <UnsupportedChartNotice chart={viz.chart} />;
}
```

`UnsupportedChartNotice` renders

```tsx
<p data-testid="eda-viz-unsupported-chart" className="text-xs text-muted-foreground">
  {`${chart} plots are not available from this compute, which returns one point per gene.`}
</p>
```

`ScatterPanel` maps the points into one `EdaScatterSeries` named "Genes" with
`x` from `effectSize` and `y` from `-log10(pValue)`, dropping a point with no
p-value, and axis labels `payload.effectSizeLabel` and `-log10(p-value)`.

`VolcanoControls` is three inputs bound to `volcanoThresholds`: a number input
labelled "Effect size threshold", a number input labelled
"Significance threshold", and a native select labelled "Direction" with the
values `upAndDown`, `upOnly`, `downOnly`. Each change calls
`setVolcanoThresholds`. The selection line renders the client count from
`selectVolcanoGenes(payload.points, thresholds, "adjustedPValue").selected.length`
with singular and plural wording, plus
`{payload.retainedPoints} of {payload.totalPoints} retained by the compute`.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/eda/cells/VizCell.test.tsx`.

**Lead note before B4.** `export_analysis_step` commits through the strategy
path, which (a) BEGINS the thread's strategy when it has none, with the EDA
step as the root, pushed on that commit, and (b) on a thread that already has
a strategy adds the EDA step as a DETACHED second root that is persisted but
never pushed to WDK until it is attached or becomes the primary root. See
[the decision](../../decisions/an-eda-export-begins-the-strategy-when-none-exists.md).
`ExportStepButton` must therefore: stay enabled on a thread with no strategy,
because the export creates one; and after a successful export beside an
existing strategy, present the step as a draft root (no WDK count, an
"Attach to strategy" affordance) rather than implying a push. Pin both with
tests.

### Task B4: export as a step

`analysis.canExportRows` is the settled gate: the backend has already checked
that the study carries exactly one `VEUPATHDB_GENE_ID` variable. The button
reads it from the store, so nothing is threaded through props.

- [ ] **Failing test.** Create
  `apps/web/src/features/eda/ExportStepButton.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { QueryClientProvider } from "@tanstack/react-query";

import { createTestQueryClient } from "@/lib/query/testing";
import { strategyQueryKey } from "@/lib/api/strategy";
import { useEdaStore } from "@/state/eda";
import { ExportStepButton } from "./ExportStepButton";

const BASE = "http://localhost:3000";
const server = setupServer();
const JOB_ID = "db04204e5386396e1ca2cb78469ab6fb";

function analysis(overrides: Record<string, unknown> = {}) {
  return {
    siteId: "plasmodb",
    datasetId: "DS_e973eadd57",
    studyId: "STUDY_e973eadd57",
    analysisId: "a-1",
    revision: 0,
    studyDisplayName: "Heat shock response",
    displayName: "Unsaved analysis",
    numFilters: 0,
    numComputations: 1,
    filters: [],
    filterSummaries: [],
    entityCounts: [],
    canExportRows: true,
    ...overrides,
  };
}

const COMPLETED_JOB = {
  jobId: JOB_ID,
  taskId: null,
  appName: "differentialexpression",
  status: "complete",
};

const STEP_RESPONSE = {
  id: "conv-1",
  siteId: "plasmodb",
  steps: [
    {
      id: "step_1",
      searchName: "GenesByEdaVizWithCompute",
      displayName: "EDA volcano, 1543 genes",
      estimatedSize: 1543,
    },
  ],
  rootStepId: "step_1",
  recordType: "transcript",
  isSaved: false,
};

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
beforeEach(() => useEdaStore.getState().reset());

describe("ExportStepButton", () => {
  it("is disabled while no compute has completed", () => {
    useEdaStore.getState().applyAnalysisState(analysis());
    render(<ExportStepButton conversationId="conv-1" />);
    expect(screen.getByRole("button", { name: "Export as step" })).toBeDisabled();
  });

  it("is disabled and says why when the analysis cannot export rows", () => {
    useEdaStore.getState().applyAnalysisState(analysis({ canExportRows: false }));
    useEdaStore.getState().applyJob(COMPLETED_JOB);
    render(<ExportStepButton conversationId="conv-1" />);
    expect(screen.getByRole("button", { name: "Export as step" })).toBeDisabled();
    expect(screen.getByTestId("eda-export-blocked")).toHaveTextContent(
      "cannot export genes",
    );
  });

  it("is disabled while the only job failed", () => {
    useEdaStore.getState().applyAnalysisState(analysis());
    useEdaStore.getState().applyJob({ ...COMPLETED_JOB, status: "failed" });
    render(<ExportStepButton conversationId="conv-1" />);
    expect(screen.getByRole("button", { name: "Export as step" })).toBeDisabled();
  });

  it("sends the export-step action with the current thresholds", async () => {
    let body: unknown = null;
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({
          analysis: analysis({ revision: 1 }),
          job: null,
          step: STEP_RESPONSE,
        });
      }),
    );
    useEdaStore.getState().applyAnalysisState(analysis());
    useEdaStore.getState().applyJob(COMPLETED_JOB);
    useEdaStore.getState().setVolcanoThresholds({
      effectSizeThreshold: 1,
      significanceThreshold: 0.05,
      direction: "upAndDown",
    });
    render(<ExportStepButton conversationId="conv-1" />);
    await userEvent.click(screen.getByRole("button", { name: "Export as step" }));
    await waitFor(() => {
      expect(body).toEqual({
        action: "export-step",
        thresholds: {
          effectSizeThreshold: 1,
          significanceThreshold: 0.05,
          effectDirection: "upAndDown",
        },
      });
    });
  });

  it("writes the returned strategy into the cache the graph already reads", async () => {
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({
          analysis: analysis({ revision: 1 }),
          job: null,
          step: STEP_RESPONSE,
        }),
      ),
    );
    const queryClient = createTestQueryClient();
    useEdaStore.getState().applyAnalysisState(analysis());
    useEdaStore.getState().applyJob(COMPLETED_JOB);
    render(
      <QueryClientProvider client={queryClient}>
        <ExportStepButton conversationId="conv-1" />
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Export as step" }));
    await waitFor(() => {
      const cached = queryClient.getQueryData(strategyQueryKey("conv-1")) as {
        steps: { id: string }[];
      };
      expect(cached.steps.map((s) => s.id)).toEqual(["step_1"]);
    });
  });

  it("applies the analysis state the export answered with", async () => {
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({
          analysis: analysis({ revision: 7 }),
          job: null,
          step: STEP_RESPONSE,
        }),
      ),
    );
    useEdaStore.getState().applyAnalysisState(analysis());
    useEdaStore.getState().applyJob(COMPLETED_JOB);
    render(<ExportStepButton conversationId="conv-1" />);
    await userEvent.click(screen.getByRole("button", { name: "Export as step" }));
    await waitFor(() => {
      expect(useEdaStore.getState().analysis?.revision).toBe(7);
    });
  });

  it("reports a failed export instead of pretending a step exists", async () => {
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({ detail: "step creation failed" }, { status: 422 }),
      ),
    );
    useEdaStore.getState().applyAnalysisState(analysis());
    useEdaStore.getState().applyJob(COMPLETED_JOB);
    render(<ExportStepButton conversationId="conv-1" />);
    await userEvent.click(screen.getByRole("button", { name: "Export as step" }));
    expect(await screen.findByTestId("eda-export-error")).toHaveTextContent(
      "step creation failed",
    );
  });
});
```

The fifth test passes its own `QueryClientProvider`: `vitest.setup.ts` wraps
every render in one, but the test needs the same client instance it inspects,
and an explicit wrapper nests inside the automatic one without harm.

- [ ] **Run and read the failure.** Expected:
  `Failed to resolve import "./ExportStepButton"`.

- [ ] **Implement** `apps/web/src/features/eda/ExportStepButton.tsx`:

```tsx
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { Strategy } from "@pathfinder/shared";

import { Button } from "@/components/ui/button";
import { patchConversationEda } from "@/lib/api/eda";
import { toUserMessage } from "@/lib/api/errors";
import { strategyQueryKey, toStrategy } from "@/lib/api/strategy";
import { isEdaJobComplete, useEdaStore } from "@/state/eda";

export function ExportStepButton({ conversationId }: { conversationId: string }) {
  const queryClient = useQueryClient();
  const jobs = useEdaStore((s) => s.jobs);
  const thresholds = useEdaStore((s) => s.volcanoThresholds);
  const canExportRows = useEdaStore((s) => s.analysis?.canExportRows ?? false);
  const applyAnalysisState = useEdaStore((s) => s.applyAnalysisState);
  const computeComplete = Object.values(jobs).some(isEdaJobComplete);

  const exportStep = useMutation({
    // The wire spells the direction effectDirection; the chart prop keeps its
    // local name, so this is the one place the two meet.
    mutationFn: () =>
      patchConversationEda(conversationId, {
        action: "export-step",
        thresholds: {
          effectSizeThreshold: thresholds.effectSizeThreshold,
          significanceThreshold: thresholds.significanceThreshold,
          effectDirection: thresholds.direction,
        },
      }),
    onSuccess: (response) => {
      if (response.analysis !== null) applyAnalysisState(response.analysis);
      if (response.step === null) return;
      queryClient.setQueryData<Strategy>(
        strategyQueryKey(conversationId),
        toStrategy(response.step),
      );
      toast.success("Step added to the strategy");
    },
    onError: (error) => toast.error(toUserMessage(error, "Export failed")),
  });

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        type="button"
        size="sm"
        disabled={!computeComplete || !canExportRows || exportStep.isPending}
        onClick={() => exportStep.mutate()}
      >
        Export as step
      </Button>
      {!canExportRows && (
        <p
          data-testid="eda-export-blocked"
          className="text-[11px] text-muted-foreground"
        >
          This study cannot export genes as a step.
        </p>
      )}
      {exportStep.error !== null && (
        <p data-testid="eda-export-error" className="text-[11px] text-destructive">
          {toUserMessage(exportStep.error, "Export failed")}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Mount it** in `EdaWorkbench`'s header actions slot with only
  `conversationId`. Coordinate the one-line edit with Implementer A; it is a
  header slot Implementer A already created.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/eda/ExportStepButton.test.tsx src/features/eda/EdaWorkbench.test.tsx`.

### Section B close-out

- [ ] `cd apps/web && yarn format`
- [ ] `npx tsc --noEmit && npx eslint src/ && node scripts/check-boundaries.mjs && node scripts/check-weak-assertions.mjs && npx vitest run`
- [ ] Report: which of the six job states the UI distinguishes and where; the
  test name and counter that prove a threshold change issues no network request;
  the test name and counter that prove polling re-issues the identical
  `run-compute` body and stops on `complete`; whether `EdaComputationSpec`
  matched batch 4's model field for field, named field by field; zero-debt
  statement or the debt.

## Verifier

Re-run:

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
yarn install --immutable
npx tsc --noEmit
npx eslint src/
node scripts/check-boundaries.mjs
node scripts/check-weak-assertions.mjs
npx vitest run
node /Users/ahmedmuharram/repos/pathfinder/scripts/check-knowledge.mjs
```

Read every created and modified file. Then hunt these traps by name:

1. **A `useEffect`**, or `useLayoutEffect` from `react`, anywhere in the diff.
2. **`useMemo`, `useCallback` or `memo`.**
3. **A component calling `fetch`.** Every EDA request must route through
   `@/lib/api/eda`.
4. **A cross-feature import from `features/eda`.** Especially
   `@/features/strategy`, which is tempting for step creation and is why
   `strategyQueryKey` and `toStrategy` live in `lib/api/strategy.ts`.
5. **A new entry in `CROSS_FEATURE_EXCEPTIONS`** in
   `scripts/check-boundaries.mjs`. Reject outright.
6. **A date bound sent without `T00:00:00`.** Grep for `dateRange` and check
   every construction goes through `edaDateBound`. A bare `YYYY-MM-DD` is a live
   500.
7. **An empty `stringSet` reaching the wire.** `isDraftApplicable` must gate it;
   the service answers a 400.
8. **A second filter appended for a variable that already has one.** Filters
   compose by AND; an edit must replace.
9. **A volcano threshold sent to the server.** The upstream volcanoplot config
   is an empty object. Any request body carrying `effectSizeThreshold` to
   `/api/v1/eda/viz` is wrong, and Task B3's counter test must exist and assert
   zero calls.
10. **`taskStatusOptions` or `tasksListOptions` imported into `features/eda`.**
    `taskId` is null for a tab-started compute; those are the chat-side
    mechanism.
11. **A poll that is not the identical `run-compute` body**, or a poll that does
    not stop on `complete`, `failed`, `expired` or `no-such-job`. Both have
    named tests in Task B2.
12. **A production interval shortened to speed a test up.**
13. **`DESeq2` used as a wire value.** Only `DESeq` and `limma` are valid;
    `DESeq2` is a display label.
14. **`identifierVariable` and `valueVariable` on different entities.** The
    plugin throws.
15. **A Radix `Select` used for the comparator, the groups or the method.** The
    task card specifies native `<select>` for `selectOption` in e2e.
16. **A count rendered without its `unfilteredCount`**, or a live count that
    survives an analysis switch.
17. **A filter read from `EdaAnalysisState.filters` rather than from the store's
    parsed `analysis.filters`**, or an `unparsedFilterCount` above zero with no
    notice on screen.
18. **`studyDisplayName` and `displayName` conflated** in the header or a cell.
19. **A `hasGeneIdVariable` prop threaded to `ExportStepButton`** instead of
    `canExportRows` read from the store.
20. **An unnamed error state.** Every failure path must have a testid and a
    message, per the named-state table. List any table row with no
    implementation.
21. **A file over 300 eslint-counted lines**, or a silenced `max-lines`.
22. **A test that asserts existence rather than a value**, and any test whose
    only matchers are weak.
23. **Smart punctuation** in any new source file, and any em dash in a comment.
24. **A study row rendering `undefined`** because `shortDisplayName` or
    `description` was assumed present.

Report format, mandatory:

```
Batch 6 verification

Gates
  tsc --noEmit              PASS/FAIL  <first error if FAIL>
  eslint src/               PASS/FAIL  <count>
  check-boundaries.mjs      PASS/FAIL  <count>
  check-weak-assertions.mjs PASS/FAIL  <count>
  vitest run                PASS/FAIL  <passed>/<total>, <duration>

Per task
  A1 route helper + yield   PASS/FAIL  <evidence>
  A2 StudyPicker            PASS/FAIL
  A3 filterDrafts           PASS/FAIL
  A4 FilterEditor           PASS/FAIL
  A5 SubsetCell             PASS/FAIL
  A6 EdaWorkbench + unbind  PASS/FAIL
  B1 computeConfig          PASS/FAIL
  B2 ComputeCell + polling  PASS/FAIL
  B3 VizCell                PASS/FAIL
  B4 ExportStepButton       PASS/FAIL

Named states  (each row of the table: implemented at <file>:<testid>, or MISSING)

Traps  (1 to 24, each CLEAN or the file:line that violates it)

Definition of done
  zero debt            YES/NO  <what remains>
  adjacent reconciled  YES/NO  <what was missed>
  tests assert values  YES/NO
```

## Exit criteria

For the session lead to close batch 6:

1. Every gate green, verified by the lead's own run.
2. `/{siteId}/conversation/{conversationId}/eda` renders `EdaWorkbench`, and
   `ChatShell` yields the main pane for it exactly as it does for `/strategy`.
3. `StudyPicker` searches, lists and binds; a bound analysis mounts
   `SubsetCell`, `ComputeCell` and `VizCell`; "Change study" sends
   `{action: "unbind"}` and resets the store only on success.
4. A filter edit in `SubsetCell` updates every entity count as
   "count of unfilteredCount" and PATCHes the analysis, and the server echo
   clears the optimistic local edit. Chips come from the store's parsed filters,
   and an unparsed filter is reported on screen.
5. The distribution sparkline picks `HistogramChart` for a continuous variable
   and `BarChart` for a categorical one, and prints `numVarValues` against
   `subsetSize`.
6. `ComputeCell` builds the differential expression config from live study
   metadata only, with `DESeq` or `limma` as the wire value, and polls by
   re-issuing the identical `run-compute` action, stopping when the job is no
   longer running. Nothing in `features/eda` imports the task-progress helpers.
7. `VizCell` thresholds the volcano client side with a test proving zero network
   calls on a threshold change, renders `scatter` from the same point cloud, and
   names `histogram`, `bar` and `boxplot` as unavailable rather than drawing
   them.
8. `ExportStepButton` gates on `analysis.canExportRows` and a complete job,
   writes the returned strategy into `strategyQueryKey(conversationId)`, and
   applies the analysis state the export answered with, all without importing
   `features/strategy`.
9. Every row of the named-state table is implemented, and the verifier's report
   shows all twenty-four traps CLEAN and "zero debt YES".
