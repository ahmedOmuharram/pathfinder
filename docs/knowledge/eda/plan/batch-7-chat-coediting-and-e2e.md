---
type: Plan
title: "Batch 7: chat co-editing and e2e"
description: The conversation part renderers that draw EDA charts inline, the right-rail entry to the tab, the co-edit loop, three end-to-end journeys, and the closure tasks that retire the plan's backlog entry.
tags: [eda, pathfinder, plan, batch, frontend, conversation, playwright, closure]
generated: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
status: accepted
---

# Batch 7: chat co-editing and e2e

**Goal:** the chat thread draws the same plots as the tab from the same data
parts, a chat-driven change moves the tab and a tab-driven change comes back as
the next analysis-state part, and three journeys prove it end to end before the
plan's backlog entry is deleted.

**Prerequisites:** batch 6 closed. This batch grows the three renderer files
batch 4 created and batch 5 wired to the store, adds one right-rail panel, and
adds no new transport.

**Read before starting:**

- [overview.md](overview.md) - the pinned shared contract. Names there are law.
- [batch-5-charts-and-state.md](batch-5-charts-and-state.md) - its "settled
  contract" section is the payload truth this batch renders, and its Produces
  blocks name every symbol used here.
- [batch-6-eda-tab.md](batch-6-eda-tab.md) - `edaTabUrl`, `isEdaRoute`, and the
  cell testids the co-edit journey drives.
- [../visualizations.md](../visualizations.md) - why volcano thresholding is
  client side.
- [../pathfinder-integration-concept.md](../pathfinder-integration-concept.md)
  and [../pathfinder-architecture-fit.md](../pathfinder-architecture-fit.md) -
  the two documents whose status lines this batch reconciles.

## The settled contract this batch renders

Quoted in full in
[batch-5-charts-and-state.md](batch-5-charts-and-state.md). The seven facts
that shape this batch:

1. `EdaAnalysisState` carries **`filterSummaries: string[]`**, already rendered
   by the backend. The chat card prints those strings; it does not summarise a
   filter itself. It also carries `numFilters`, `numComputations`,
   `studyDisplayName` (the study title), `displayName` (the analysis's own
   name), `canExportRows`, and `entityCounts` with both `count` and
   `unfilteredCount`.
2. `EdaSubsetPreviewPart` is
   `{ datasetId, analysisId, entityCounts, distribution }`. There is no single
   `count`, no `total` and no bin objects: the card prints one row per
   `entityCounts` entry as "count of unfilteredCount entityDisplayName", and the
   distribution as parallel `labels` and `values` arrays.
3. `EdaVizPart` is a point cloud plus thresholds:
   `{ datasetId, analysisId, chart, effectSizeLabel, effectSizeThreshold,
   significanceThreshold, effectDirection, totalPoints, retainedPoints, points }`,
   a point being `{ pointId, effectSize, pValue?, adjustedPValue?, retained }`
   with **numbers**. The durable compute completion emits `data-eda.viz` at the
   default thresholds right after its `data-eda.analysis-state` part, so the
   chat card and the tab's store both receive a real volcano without a fixture.
4. `chart` is `volcano | histogram | boxplot | bar | scatter`. Only `volcano`
   and `scatter` are renderable from a point cloud; the other three get a named
   notice.
5. `effectDirection` is `upOnly | downOnly | upAndDown`, the same vocabulary the
   chart props use.
6. The tab's `PATCH /api/v1/conversations/{id}/eda` **writes no conversation
   event**. Chat therefore reflects a tab edit on the agent's next
   `data-eda.analysis-state` part, which the store's reconcile rule handles.
7. `EdaVariableResponse` carries `hideFrom: string[]` beside the filter fields,
   and the tab's entity tree hides a variable whose `hideFrom` names
   `everywhere` or `variableTree`; the chat tools still list and filter it.

## Inherited constraints

Copied here so no implementer needs another file.

**TDD is non-negotiable.** No production code without a failing test first.
**Divide and conquer first:** prove wiring with pure and jsdom tests, then
reserve Playwright for the confirmations named in this document. A journey that
could have been a jsdom test and was written as a browser test is a task
failure.

**React rules, enforced by `eslint.config.cjs`:** `useEffect` is banned by
`no-restricted-imports`; `useMemo`, `useCallback` and `memo` are banned because
React Compiler is on; imperative mounting uses a ref callback that returns its
teardown. Replacements in use: a TanStack Query `queryFn` for a one-shot side
effect (`features/conversation/content/parts/DataBackgroundTaskStarted.tsx`), a
render-time `setState` plus `queueMicrotask`
(`features/conversation/rail/RightRail.tsx` lines 61-69).

**Other eslint rules that will fail a careless edit:** `max-lines` 300 per
production file (test files are exempt),
`@typescript-eslint/strict-boolean-expressions`,
`@typescript-eslint/no-unnecessary-condition`,
`@typescript-eslint/switch-exhaustiveness-check`,
`consistent-type-imports`, `no-console` except `warn` and `error`.

**tsconfig strictness:** `strict`, `noUncheckedIndexedAccess`,
`exactOptionalPropertyTypes`, `noPropertyAccessFromIndexSignature`.

**No type suppressions**, and `as any` is refused by
`scripts/check-boundaries.mjs` rule 2. **No `import as`.**

**Frontend boundaries:** `features/conversation` may import `features/settings`,
`engine`, `strategy`, `workbench`, `saved` and `analysis` per
`CROSS_FEATURE_EXCEPTIONS` in `scripts/check-boundaries.mjs`. It may **not**
import `features/eda`, and this batch does not add that exemption: the rail
panel and the renderers reach the tab through `@/state/eda`,
`@/lib/components/charts/` and `@/lib/routes`, all already allowed.

**Playwright rules:**

- `scripts/check-no-first-nth.mjs` fails any `.first(`, `.nth(` or `.last(` in
  an `e2e/**/*.spec.ts` file without a `TODO(weak-strict-mode)` marker. Fix a
  strict-mode collision with a more specific locator, never with an index. The
  precedent for resolving one properly is `GraphPage.firstRailStepId` in
  `apps/web/e2e/pages/graph.page.ts`, which reads the ids out of the DOM with
  `evaluateAll` instead.
- A native `<select>` is driven with `locator.selectOption(value)`, never
  click plus option.
- SSE needs the webpack dev server: run the web app with `next dev --webpack`.
  Turbopack buffers the stream and every SSE assertion times out.
- `context.request` shares the page's cookies; the standalone `request` fixture
  does not.
- Check the Playwright docs before changing a failing test. No guessing.

**Only the LLM is mocked.** Two lanes, and the overview authorises both:
"Live-EDA tests follow the `reference_wdk_live_test_suite` pattern: hermetic
tests run against recorded wire fixtures (checked in under the test tree);
live-lane tests are opt-in via environment flag and re-fetch to catch drift."
So a spec may `page.route` the `/api/v1/eda/*` endpoints with recorded
payloads, and the same spec re-runs against the live service when
`PATHFINDER_EDA_LIVE=1` is set.

**Comments:** 1 to 3 lines maximum, simple present tense. No narration, no
history, no dates, no names.

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
node scripts/check-no-first-nth.mjs
npx vitest run <exact test files for this task>
```

## Implementer A: part renderers, the rail entry, and the co-edit loop

### Files

**Modify**

- `apps/web/src/features/conversation/content/parts/DataEdaViz.tsx`
- `apps/web/src/features/conversation/content/parts/DataEdaAnalysisState.tsx`
- `apps/web/src/features/conversation/content/parts/DataEdaSubsetPreview.tsx`
- `apps/web/src/features/conversation/content/parts/DataEdaAnalysisState.test.tsx`
- `apps/web/src/features/conversation/rail/RightRail.tsx`
- `apps/web/src/features/conversation/rail/railActivity.ts`
- `apps/web/src/features/conversation/rail/railActivity.test.ts`
- `apps/web/src/state/useRightRailStore.ts`
- `apps/web/src/state/useRightRailStore.test.ts`

**Create**

- `apps/web/src/features/conversation/content/parts/DataEdaViz.test.tsx`
- `apps/web/src/features/conversation/content/parts/DataEdaSubsetPreview.test.tsx`
- `apps/web/src/features/conversation/content/parts/edaPartFixtures.ts`
- `apps/web/src/features/conversation/rail/EdaPanel.tsx`
- `apps/web/src/features/conversation/rail/EdaPanel.test.tsx`

Batch 4 created the three renderer files at text-only fidelity and registered
them in `content/edaDataParts.ts` and `content/contentComponents.ts`. Batch 5
added `useHydrateEdaPart` to each. Neither registration file changes here; only
the three components' bodies grow.

### Interfaces

**Consumes:**

```ts
import { VolcanoChart } from "@/lib/components/charts/VolcanoChart";
import { ScatterChart } from "@/lib/components/charts/ScatterChart";
import { HistogramChart } from "@/lib/components/charts/HistogramChart";
import type { EdaScatterSeries } from "@/lib/components/charts/types";
import { selectVolcanoGenes } from "@/lib/eda/volcanoSelection";
import { useEdaStore, useHydrateEdaPart } from "@/state/eda";
import { useConversationId } from "@/lib/hooks/useConversationId";
import { edaTabUrl } from "@/lib/routes";
```

The chat card needs no filter-summarising helper: the analysis-state part
carries `filterSummaries`, which the backend rendered. `filterSummary` in
`features/eda/filterDrafts.ts` stays where it is, for the tab's editable chips,
which need `entityId` and `variableId` to open an editor. Do not hoist it: the
two callers want different strings, and one shared function serving both would
grow a mode flag.

**Produces:** the three grown renderers, `EdaPanel`, and the new
`RightRailPanel` member `"eda"`.

### The reconcile rule, stated once

Batch 5's `applyAnalysisState` implements it and has it under test. This batch
depends on it and adds no second rule:

- **The server part always wins.** A `data-eda.analysis-state` part clears
  `localFilters`, so an optimistic tab edit disappears the moment the server
  echoes the document.
- **Keyed by `analysisId` plus `revision`**, a per-binding integer mutation
  counter. A part naming a lower `revision` of the same `analysisId` is ignored,
  because SSE reconnects replay. An equal revision is accepted.
- **A different `analysisId` replaces wholesale**, whatever the revision, and
  clears the subset preview, the plots, the jobs and the adopted thresholds.
- **Last write wins when either side's `revision` is null.**

### Task A1: DataEdaViz draws the plot the payload allows

- [ ] **Create the shared fixtures first**,
  `apps/web/src/features/conversation/content/parts/edaPartFixtures.ts`:

```ts
import type {
  EdaAnalysisState,
  EdaSubsetPreviewPart,
  EdaVizPart,
} from "@pathfinder/shared";

export const EDA_ANALYSIS_STATE_FIXTURE: EdaAnalysisState = {
  siteId: "plasmodb",
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  analysisId: "a-1",
  revision: 3,
  studyDisplayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
  displayName: "Febrile samples",
  numFilters: 2,
  numComputations: 1,
  filters: [
    {
      entityId: "ENT_8151325d",
      variableId: "VAR_081ab087",
      type: "stringSet",
      stringSet: ["febrile"],
    },
    {
      entityId: "ENT_8151325d",
      variableId: "VAR_7033e90f",
      type: "numberRange",
      min: 37,
      max: 42,
    },
  ],
  filterSummaries: [
    "temperature_condition is febrile",
    "Temperature is 37 to 42",
  ],
  entityCounts: [
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
  ],
  canExportRows: true,
};

export const EDA_SUBSET_PREVIEW_FIXTURE: EdaSubsetPreviewPart = {
  datasetId: "DS_e973eadd57",
  analysisId: "a-1",
  entityCounts: [
    {
      entityId: "ENT_8151325d",
      entityDisplayName: "Sample",
      count: 6,
      unfilteredCount: 12,
    },
  ],
  distribution: {
    variableId: "VAR_7033e90f",
    variableDisplayName: "Temperature",
    labels: ["[37, 38)", "[41, 42]"],
    values: [6, 6],
    subsetSize: 6,
    numVarValues: 6,
    numMissingCases: 0,
    isMultiValued: false,
  },
};

export const EDA_VOLCANO_VIZ_FIXTURE: EdaVizPart = {
  datasetId: "DS_e973eadd57",
  analysisId: "a-1",
  chart: "volcano",
  effectSizeLabel: "log2(Fold Change)",
  effectSizeThreshold: 1,
  significanceThreshold: 0.05,
  effectDirection: "upAndDown",
  totalPoints: 3,
  retainedPoints: 1,
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
      pointId: "PF3D7_MIT04200",
      effectSize: -1.49447459261845,
      retained: false,
    },
  ],
};

export const EDA_SCATTER_VIZ_FIXTURE: EdaVizPart = {
  ...EDA_VOLCANO_VIZ_FIXTURE,
  chart: "scatter",
};
```

At the fixture's own thresholds the client selection is
`["PF3D7_0100200"]`, which matches `retainedPoints: 1`, and
`PF3D7_MIT04200` is dropped for carrying no p-value.

- [ ] **Failing test.** Create
  `apps/web/src/features/conversation/content/parts/DataEdaViz.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/components/charts/echartsRegistry", () => ({
  initChart: () => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
  }),
}));

import { useEdaStore } from "@/state/eda";
import { DataEdaViz } from "./DataEdaViz";
import {
  EDA_ANALYSIS_STATE_FIXTURE,
  EDA_SCATTER_VIZ_FIXTURE,
  EDA_VOLCANO_VIZ_FIXTURE,
} from "./edaPartFixtures";

beforeEach(() => {
  useEdaStore.getState().reset();
  useEdaStore.getState().applyAnalysisState(EDA_ANALYSIS_STATE_FIXTURE);
});

describe("DataEdaViz volcano", () => {
  it("names the plot and draws the volcano", () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    expect(screen.getByTestId("data-eda-viz")).toHaveTextContent(
      "log2(Fold Change)",
    );
    expect(screen.getByTestId("eda-viz-volcano")).toHaveAttribute("role", "img");
  });

  it("reports the client selection and the compute's own retained count", () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    const line = screen.getByTestId("eda-viz-volcano-selection");
    expect(line).toHaveTextContent("1 gene selected");
    expect(line).toHaveTextContent("1 of 3 retained by the compute");
  });

  it("caps the collapsed height and expands on request", async () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    expect(screen.getByTestId("eda-viz-volcano")).toHaveStyle({ height: "220px" });
    await userEvent.click(screen.getByRole("button", { name: "Expand plot" }));
    expect(screen.getByTestId("eda-viz-volcano")).toHaveStyle({ height: "480px" });
    expect(screen.getByRole("button", { name: "Collapse plot" })).toBeInTheDocument();
  });

  it("hydrates the store so the tab shows the same plot", async () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    await waitFor(() => {
      expect(useEdaStore.getState().viz["volcano"]?.retainedPoints).toBe(1);
    });
  });

  it("reports the point it could not plot", () => {
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    expect(screen.getByTestId("eda-viz-volcano-dropped")).toHaveTextContent(
      "1 point without a p-value was not plotted",
    );
  });

  it("uses the thresholds the tab set, so both surfaces agree", () => {
    useEdaStore.getState().setVolcanoThresholds({
      effectSizeThreshold: 4,
      significanceThreshold: 0.05,
      direction: "upAndDown",
    });
    render(<DataEdaViz data={EDA_VOLCANO_VIZ_FIXTURE} />);
    expect(screen.getByTestId("eda-viz-volcano-selection")).toHaveTextContent(
      "0 genes selected",
    );
  });
});

describe("DataEdaViz other charts", () => {
  it("draws the scatter and names both axes", () => {
    render(<DataEdaViz data={EDA_SCATTER_VIZ_FIXTURE} />);
    expect(screen.getByTestId("eda-viz-scatter")).toHaveAttribute(
      "aria-label",
      "log2(Fold Change) against -log10(p-value), 2 points",
    );
  });

  it("says a bar plot cannot be drawn from a point cloud", () => {
    render(<DataEdaViz data={{ ...EDA_VOLCANO_VIZ_FIXTURE, chart: "bar" }} />);
    expect(screen.getByTestId("data-eda-viz-unsupported-chart")).toHaveTextContent(
      "bar plots are not available from this compute",
    );
  });

  it("says the same for a histogram and a boxplot", () => {
    const { unmount } = render(
      <DataEdaViz data={{ ...EDA_VOLCANO_VIZ_FIXTURE, chart: "histogram" }} />,
    );
    expect(screen.getByTestId("data-eda-viz-unsupported-chart")).toHaveTextContent(
      "histogram plots are not available from this compute",
    );
    unmount();
    render(<DataEdaViz data={{ ...EDA_VOLCANO_VIZ_FIXTURE, chart: "boxplot" }} />);
    expect(screen.getByTestId("data-eda-viz-unsupported-chart")).toHaveTextContent(
      "boxplot plots are not available from this compute",
    );
  });

  it("says so when the payload carries no points at all", () => {
    render(<DataEdaViz data={{ ...EDA_VOLCANO_VIZ_FIXTURE, points: [] }} />);
    expect(screen.getByTestId("data-eda-viz-empty")).toHaveTextContent(
      "This compute returned no points",
    );
  });
});
```

The scatter aria label says 2 points because `PF3D7_MIT04200` has no p-value and
is dropped. At `effectSizeThreshold: 4` nothing qualifies, which is the
"0 genes selected" case.

- [ ] **Run and read the failure.**
  `npx vitest run src/features/conversation/content/parts/DataEdaViz.test.tsx`
  Expected: `Unable to find an element by: [data-testid="eda-viz-volcano"]`,
  because batch 4's `DataEdaViz` renders only text.

- [ ] **Implement.** Grow `DataEdaViz.tsx`, dispatching on `chart` with a
  `switch` so a sixth value fails compilation.

```tsx
"use client";

import { useState } from "react";
import { ChevronsDownUp, ChevronsUpDown } from "lucide-react";
import type { EdaVizPart } from "@pathfinder/shared";

import { Button } from "@/components/ui/button";
import { useEdaStore, useHydrateEdaPart } from "@/state/eda";

const COLLAPSED_HEIGHT = 220;
const EXPANDED_HEIGHT = 480;

export function DataEdaViz({ data }: { data: EdaVizPart }) {
  useHydrateEdaPart({ kind: "viz", data });
  const thresholds = useEdaStore((s) => s.volcanoThresholds);
  const [expanded, setExpanded] = useState(false);
  const height = expanded ? EXPANDED_HEIGHT : COLLAPSED_HEIGHT;

  return (
    <div
      data-testid="data-eda-viz"
      className="my-2 rounded-md border border-border bg-card p-3"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium">{data.effectSizeLabel}</span>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label={expanded ? "Collapse plot" : "Expand plot"}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? (
            <ChevronsDownUp className="size-3.5" aria-hidden />
          ) : (
            <ChevronsUpDown className="size-3.5" aria-hidden />
          )}
        </Button>
      </div>
      <VizBody data={data} height={height} thresholds={thresholds} />
    </div>
  );
}
```

`VizBody` returns the empty notice when `data.points.length === 0`, then
switches:

- `volcano` renders `VolcanoChart` with `points={data.points}`,
  `thresholds`, `significanceField="adjustedPValue"`,
  `effectSizeLabel={data.effectSizeLabel}`, `testId="eda-viz-volcano"`, plus a
  selection line with `data-testid="eda-viz-volcano-selection"` reading
  `selectVolcanoGenes(data.points, thresholds, "adjustedPValue").selected.length`
  and `{data.retainedPoints} of {data.totalPoints} retained by the compute`.
- `scatter` maps the points into one `EdaScatterSeries` named "Genes" with `x`
  from `effectSize` and `y` from `-Math.log10(pValue)`, dropping a point whose
  p-value is absent, null or not above zero, and renders `ScatterChart` with
  `xAxis={{ variableId: "effectSize", displayName: data.effectSizeLabel }}` and
  `yAxis={{ variableId: "pValue", displayName: "-log10(p-value)" }}`,
  `testId="eda-viz-scatter"`. `ScatterChart` composes its own aria label as
  `"<x> against <y>, <n> points"`.
- `histogram`, `bar` and `boxplot` render

```tsx
<p
  data-testid="data-eda-viz-unsupported-chart"
  className="text-[11px] text-muted-foreground"
>
  {`${data.chart} plots are not available from this compute, which returns one point per gene.`}
</p>
```

Batch 6 renders exactly the same three notices in `VizCell`. That is two
call sites for one sentence, and the sentence lives in each because the two
surfaces are in different features and the string is not a shared concept worth
a `lib/` module. If a third caller appears, hoist it then, not now.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/conversation/content/parts/DataEdaViz.test.tsx`.

### Task A2: the analysis-state card and its open-in-tab affordance

- [ ] **Failing test.** Extend
  `apps/web/src/features/conversation/content/parts/DataEdaAnalysisState.test.tsx`,
  which batch 5 created, replacing its inline payload with the shared fixture
  and adding:

```tsx
import { edaTabUrl } from "@/lib/routes";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/plasmodb/conversation/conv-1",
}));

describe("DataEdaAnalysisState chips and navigation", () => {
  it("names the study and the analysis separately", () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    const card = screen.getByTestId("data-eda-analysis-state");
    expect(card).toHaveTextContent(
      "Heat shock response in sensitive mutants (LRR5, DHC)",
    );
    expect(card).toHaveTextContent("Febrile samples");
  });

  it("renders one chip per backend filter summary, in order", () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    const chips = screen.getAllByTestId(/^data-eda-filter-chip-/);
    expect(chips).toHaveLength(2);
    expect(chips[0]).toHaveTextContent("temperature_condition is febrile");
    expect(chips[1]).toHaveTextContent("Temperature is 37 to 42");
  });

  it("prints each entity count against its unfiltered total", () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    const card = screen.getByTestId("data-eda-analysis-state");
    expect(card).toHaveTextContent("6 of 12 Sample");
    expect(card).toHaveTextContent("34,320 of 68,640 pfal3D7 htseq counts");
  });

  it("says the subset is unfiltered when there are no summaries", () => {
    render(
      <DataEdaAnalysisState
        data={{
          ...EDA_ANALYSIS_STATE_FIXTURE,
          numFilters: 0,
          filters: [],
          filterSummaries: [],
        }}
      />,
    );
    expect(screen.getByTestId("data-eda-analysis-state")).toHaveTextContent(
      "No filters yet",
    );
  });

  it("says how many filters the backend counted when it rendered fewer summaries", () => {
    render(
      <DataEdaAnalysisState
        data={{ ...EDA_ANALYSIS_STATE_FIXTURE, numFilters: 5 }}
      />,
    );
    expect(screen.getByTestId("data-eda-filter-overflow")).toHaveTextContent(
      "3 more filters",
    );
  });

  it("opens the EDA tab for the conversation in the path", async () => {
    render(<DataEdaAnalysisState data={EDA_ANALYSIS_STATE_FIXTURE} />);
    await userEvent.click(screen.getByRole("button", { name: "Open in EDA tab" }));
    expect(pushMock).toHaveBeenCalledWith(edaTabUrl("plasmodb", "conv-1"));
  });
});
```

and, in a second file-level `describe` that re-mocks `next/navigation` with
`usePathname: () => "/plasmodb/workbench"`, one case asserting
`screen.queryByRole("button", { name: "Open in EDA tab" })` is `null` when
`useConversationId()` finds no conversation.

- [ ] **Run and read the failure.** Expected:
  `Unable to find an element by: [data-testid=/^data-eda-filter-chip-/]`.

- [ ] **Implement.** Grow `DataEdaAnalysisState.tsx`. The chips come straight
  from `filterSummaries`; the card summarises nothing itself. Key each chip by
  its index, since a summary string is not an id:
  `data-testid={"data-eda-filter-chip-" + index}`. When
  `numFilters > filterSummaries.length`, print the overflow line
  `data-testid="data-eda-filter-overflow"` reading
  `{numFilters - filterSummaries.length} more filters`. The site id comes from
  `data.siteId` and the conversation id from `useConversationId()`.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/conversation/content/parts/DataEdaAnalysisState.test.tsx`.

### Task A3: the subset-preview card

- [ ] **Failing test.** Create
  `apps/web/src/features/conversation/content/parts/DataEdaSubsetPreview.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/components/charts/echartsRegistry", () => ({
  initChart: () => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
  }),
}));

import { useEdaStore } from "@/state/eda";
import { DataEdaSubsetPreview } from "./DataEdaSubsetPreview";
import {
  EDA_ANALYSIS_STATE_FIXTURE,
  EDA_SUBSET_PREVIEW_FIXTURE,
} from "./edaPartFixtures";

beforeEach(() => {
  useEdaStore.getState().reset();
  useEdaStore.getState().applyAnalysisState(EDA_ANALYSIS_STATE_FIXTURE);
});

describe("DataEdaSubsetPreview", () => {
  it("prints each entity count against its unfiltered total", () => {
    render(<DataEdaSubsetPreview data={EDA_SUBSET_PREVIEW_FIXTURE} />);
    expect(screen.getByTestId("data-eda-subset-preview")).toHaveTextContent(
      "6 of 12 Sample",
    );
  });

  it("draws the distribution as a mini histogram named after the variable", () => {
    render(<DataEdaSubsetPreview data={EDA_SUBSET_PREVIEW_FIXTURE} />);
    expect(screen.getByTestId("data-eda-subset-histogram")).toHaveAttribute(
      "aria-label",
      "Temperature distribution over the subset",
    );
  });

  it("reports how many records carry a value", () => {
    render(<DataEdaSubsetPreview data={EDA_SUBSET_PREVIEW_FIXTURE} />);
    expect(screen.getByTestId("data-eda-subset-coverage")).toHaveTextContent(
      "6 of 6 records have a value",
    );
  });

  it("warns when the variable is multi-valued, because the bars do not add up", () => {
    render(
      <DataEdaSubsetPreview
        data={{
          ...EDA_SUBSET_PREVIEW_FIXTURE,
          distribution: {
            ...EDA_SUBSET_PREVIEW_FIXTURE.distribution!,
            isMultiValued: true,
            numVarValues: 9,
          },
        }}
      />,
    );
    expect(screen.getByTestId("data-eda-subset-multivalued")).toHaveTextContent(
      "one record can carry several values",
    );
  });

  it("omits the histogram when the part carries no distribution", () => {
    render(
      <DataEdaSubsetPreview
        data={{ ...EDA_SUBSET_PREVIEW_FIXTURE, distribution: null }}
      />,
    );
    expect(screen.queryByTestId("data-eda-subset-histogram")).toBe(null);
    expect(screen.getByTestId("data-eda-subset-preview")).toHaveTextContent(
      "6 of 12 Sample",
    );
  });

  it("hydrates the store", async () => {
    render(<DataEdaSubsetPreview data={EDA_SUBSET_PREVIEW_FIXTURE} />);
    await waitFor(() => {
      expect(
        useEdaStore.getState().subsetPreview?.entityCounts[0]?.count,
      ).toBe(6);
    });
  });
});
```

- [ ] **Run and read the failure.** Expected the count-format assertion to fail
  against batch 4's text-only body.

- [ ] **Implement.** Grow `DataEdaSubsetPreview.tsx`: one line per
  `entityCounts` entry as "count of unfilteredCount entityDisplayName" with
  `toLocaleString()` on both numbers, then `HistogramChart` at `height={72}`,
  `barMode="stack"`, `series={[{ name: distribution.variableDisplayName, labels: distribution.labels, values: distribution.values }]}`,
  then the coverage line and the multi-valued warning. The coverage line
  prints plain unformatted integers (8409 of 4279), while the entity count
  rows use toLocaleString - the acceptance suite compares comma-stripped
  text, so only this document fixes the choice. The card always uses
  `HistogramChart`, because the part carries no `dataShape` to choose a form
  from; the tab, which has the variable node in hand, chooses between histogram
  and bar.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/conversation/content/parts/DataEdaSubsetPreview.test.tsx`.

### Task A4: the right-rail EDA entry

- [ ] **Failing test.** Extend
  `apps/web/src/state/useRightRailStore.test.ts`:

```ts
import { RIGHT_RAIL_PANELS } from "./useRightRailStore";

describe("RIGHT_RAIL_PANELS", () => {
  it("carries the eda panel", () => {
    expect(RIGHT_RAIL_PANELS).toEqual([
      "strategy",
      "tasks",
      "memories",
      "scratchpad",
      "ledger",
      "eda",
    ]);
  });
});
```

and `apps/web/src/features/conversation/rail/railActivity.test.ts`:

```ts
describe("computeRailActivity eda", () => {
  it("counts every eda part towards the eda panel", () => {
    const activity = computeRailActivity([
      {
        role: "assistant",
        parts: [
          { type: "data-eda.analysis-state" },
          { type: "data-eda.subset-preview" },
          { type: "data-eda.viz" },
        ],
      },
    ]);
    expect(activity.edaCount).toBe(3);
  });

  it("is zero when no eda part arrived", () => {
    const activity = computeRailActivity([
      { role: "assistant", parts: [{ type: "data-task-progress" }] },
    ]);
    expect(activity.edaCount).toBe(0);
  });
});
```

and create `apps/web/src/features/conversation/rail/EdaPanel.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => "/plasmodb/conversation/conv-1",
}));

import { useEdaStore } from "@/state/eda";
import { EdaPanel } from "./EdaPanel";
import { EDA_ANALYSIS_STATE_FIXTURE } from "../content/parts/edaPartFixtures";

beforeEach(() => {
  useEdaStore.getState().reset();
  pushMock.mockClear();
});

describe("EdaPanel", () => {
  it("invites the researcher to ask for a study when nothing is bound", () => {
    render(<EdaPanel conversationId="conv-1" siteId="plasmodb" />);
    expect(screen.getByTestId("rail-eda-panel")).toHaveTextContent(
      "No EDA analysis is open",
    );
  });

  it("names the bound study, the analysis and its filter count", () => {
    useEdaStore.getState().applyAnalysisState(EDA_ANALYSIS_STATE_FIXTURE);
    render(<EdaPanel conversationId="conv-1" siteId="plasmodb" />);
    const panel = screen.getByTestId("rail-eda-panel");
    expect(panel).toHaveTextContent(
      "Heat shock response in sensitive mutants (LRR5, DHC)",
    );
    expect(panel).toHaveTextContent("Febrile samples");
    expect(panel).toHaveTextContent("2 filters");
    expect(panel).toHaveTextContent("1 computation");
  });

  it("opens the tab from the header action", async () => {
    useEdaStore.getState().applyAnalysisState(EDA_ANALYSIS_STATE_FIXTURE);
    render(<EdaPanel conversationId="conv-1" siteId="plasmodb" />);
    await userEvent.click(screen.getByTestId("rail-eda-open"));
    expect(pushMock).toHaveBeenCalledWith("/plasmodb/conversation/conv-1/eda");
  });

  it("has no open action when nothing is bound", () => {
    render(<EdaPanel conversationId="conv-1" siteId="plasmodb" />);
    expect(screen.queryByTestId("rail-eda-open")).toBe(null);
  });
});
```

- [ ] **Run and read the failure.** Expected:
  `Failed to resolve import "./EdaPanel"`, plus the `RIGHT_RAIL_PANELS` and
  `edaCount` failures.

- [ ] **Implement.** Four coordinated edits, each forced by a compile error, so
  none can be forgotten:

  1. `apps/web/src/state/useRightRailStore.ts`: append `"eda"` to
     `RIGHT_RAIL_PANELS` and add `edaCount: number` to `LastSeen` and
     `DEFAULT_LAST_SEEN`.
  2. `apps/web/src/features/conversation/rail/railActivity.ts`: add
     `edaCount` to `RailActivity`, to the initial object, and three entries to
     `PART_TO_KEY` mapping `"data-eda.analysis-state"`,
     `"data-eda.subset-preview"` and `"data-eda.viz"` to `"edaCount"`.
  3. `apps/web/src/features/conversation/rail/RightRail.tsx`: add
     `{ id: "eda", icon: FlaskConical, label: "EDA" }` to `RAIL_ICONS`, add
     `eda: activity.edaCount !== lastSeen.edaCount` to the `hasUpdate` record,
     add `case "eda": return { edaCount: activity.edaCount };` to `markersFor`
     (the switch is exhaustive over `RightRailPanel`, so `tsc` demands it), and
     `{openPanel === "eda" && <EdaPanel conversationId={conversationId} siteId={siteId} />}`
     to the panel body.
  4. `apps/web/src/features/conversation/rail/EdaPanel.tsx`, built on
     `RailPanelShell` and `RailEmptyState` from `./RailPanelShell`, with a
     `headerActions` button carrying `data-testid="rail-eda-open"` that calls
     `router.push(edaTabUrl(siteId, conversationId))`. `StrategyPanel.tsx` is
     the shape to copy, including its `router.push` inside a local function.
     The body reads `analysis.studyDisplayName`, `analysis.displayName`,
     `analysis.numFilters` and `analysis.numComputations` from
     `useEdaStore`, with singular and plural wording on both counts.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/state/useRightRailStore.test.ts src/features/conversation/rail/railActivity.test.ts src/features/conversation/rail/EdaPanel.test.tsx`.

### Section A close-out

- [ ] `cd apps/web && yarn format`
- [ ] `npx tsc --noEmit && npx eslint src/ && node scripts/check-boundaries.mjs && node scripts/check-weak-assertions.mjs && npx vitest run`
- [ ] Report: the four coordinated rail edits with the compile error each one
  answered; the testids section B's e2e will target; zero-debt statement or the
  debt.

## Implementer B: journeys and closure

### Files

**Create**

- `apps/web/e2e/fixtures/eda.ts`
- `apps/web/e2e/feature/eda-chat-parts.spec.ts`
- `apps/web/e2e/feature/eda-coedit.spec.ts`
- `apps/web/e2e/feature/eda-export-step.spec.ts`

**Modify**

- nothing in `src/`. If a journey needs a production change, stop and report it
  rather than editing: an e2e-driven production edit belongs in a task card, and
  section A owns those files.

### Why the chat turn is route-mocked and the backend mock is not touched

`apps/web/e2e/feature/durable-verification.spec.ts` is the pattern: it builds
the SSE tail by hand with `sseFrame` and `sseDone` from
`apps/web/e2e/fixtures/sse.ts` and fulfils `page.route("**/api/v1/chat")` with
it. That proves exactly the rendering path these journeys need, needs no new
scripted turn in `apps/api/src/pathfinder/ai/models/`, and cannot drift when a
prompt changes. `apps/web/e2e/fixtures/sse.ts` already documents the frame
shape: `id: <cursor>` plus `data: <payload>` plus a blank line, with a cursor
counter starting far above any real event id so a mocked tail sorts after the
snapshot.

Three consequences to respect:

- The mocked tail's `[DONE]` cursor is persisted per thread, so **a spec must
  not read a real tail on a thread it already answered with a mocked one.** Use
  one fresh conversation per test.
- The chat route is mocked, so the LLM is the only mocked thing in journey 1.
- Journeys 2 and 3 drive the tab, whose requests hit `/api/v1/eda/*` and
  `PATCH /api/v1/conversations/{id}/eda`. Those are answered from recorded
  payloads in the hermetic lane and from the live service when
  `PATHFINDER_EDA_LIVE=1`.

### The host stack these specs need

```
PATHFINDER_CHAT_PROVIDER=mock
web:    cd apps/web && npx next dev --webpack
api:    the api container or a host uvicorn
worker: required - chat turns run on the chat_turn queue
```

Turbopack buffers SSE, so `--webpack` is not optional. If chat hangs, check the
worker first.

### Task B1: the shared EDA route fixtures

- [ ] **Implement** `apps/web/e2e/fixtures/eda.ts`. This file has no test of
  its own; the three specs are its tests.

```ts
import type { Page } from "@playwright/test";

export const EDA_LIVE = process.env["PATHFINDER_EDA_LIVE"] === "1";

export const STUDY_ROW = {
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  displayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
  shortDisplayName: "Heat shock",
  lastModified: "2026-05-27T20:00:00-04:00",
  sourceType: "curated",
};

export const STUDY_DETAIL = {
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  displayName: STUDY_ROW.displayName,
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
  },
};

export const COUNTS_UNFILTERED = [
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

export const COUNTS_FEBRILE = [
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

export const FEBRILE_FILTER = {
  entityId: "ENT_8151325d",
  variableId: "VAR_081ab087",
  type: "stringSet",
  stringSet: ["febrile"],
};

export function analysisState(overrides: Record<string, unknown> = {}) {
  return {
    siteId: "plasmodb",
    datasetId: "DS_e973eadd57",
    studyId: "STUDY_e973eadd57",
    analysisId: "a-e2e-1",
    revision: 0,
    studyDisplayName: STUDY_ROW.displayName,
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

export const VOLCANO_VIZ = {
  datasetId: "DS_e973eadd57",
  analysisId: "a-e2e-1",
  chart: "volcano",
  effectSizeLabel: "log2(Fold Change)",
  effectSizeThreshold: 1,
  significanceThreshold: 0.05,
  effectDirection: "upAndDown",
  totalPoints: 3,
  retainedPoints: 1,
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
    { pointId: "PF3D7_MIT04200", effectSize: -1.49447459261845, retained: false },
  ],
};

export const SUBSET_PREVIEW = {
  datasetId: "DS_e973eadd57",
  analysisId: "a-e2e-1",
  entityCounts: COUNTS_FEBRILE,
  distribution: {
    variableId: "VAR_081ab087",
    variableDisplayName: "temperature_condition",
    labels: ["febrile"],
    values: [6],
    subsetSize: 6,
    numVarValues: 6,
    numMissingCases: 0,
    isMultiValued: false,
  },
};

/** Answer the tab's EDA reads from recorded payloads. No-op in the live lane. */
export async function routeEdaReads(page: Page): Promise<void> {
  if (EDA_LIVE) return;
  await page.route("**/api/v1/eda/studies?*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ studies: [STUDY_ROW] }),
    }),
  );
  await page.route("**/api/v1/eda/studies/DS_e973eadd57*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(STUDY_DETAIL),
    }),
  );
  await page.route("**/api/v1/eda/count", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ counts: COUNTS_FEBRILE }),
    }),
  );
  await page.route("**/api/v1/eda/distribution", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SUBSET_PREVIEW.distribution),
    }),
  );
}
```

The study-search pattern must be `**/api/v1/eda/studies?*` so it does not also
swallow `**/api/v1/eda/studies/DS_...`; register the detail route second so its
more specific pattern wins on Playwright's last-registered-first order. Verify
that ordering against the Playwright docs before relying on it.

### Task B2: journey 1, the chat-only render

- [ ] **Failing test.** Create
  `apps/web/e2e/feature/eda-chat-parts.spec.ts`:

```ts
import { test, expect, BASE_URL } from "../fixtures/test";
import { sseDone, sseFrame, uiMessageStreamHeaders } from "../fixtures/sse";
import {
  analysisState,
  FEBRILE_FILTER,
  SUBSET_PREVIEW,
  VOLCANO_VIZ,
} from "../fixtures/eda";
import { CSRF_HEADERS } from "../fixtures/api-client";
import type { BrowserContext } from "@playwright/test";

async function openConversation(context: BrowserContext): Promise<string> {
  const resp = await context.request.post(`${BASE_URL}/api/v1/conversations/open`, {
    data: { siteId: "plasmodb" },
    headers: CSRF_HEADERS,
  });
  if (!resp.ok()) throw new Error(`open failed: ${resp.status()}`);
  const body = (await resp.json()) as { conversationId?: string; id?: string };
  const id = body.conversationId ?? body.id;
  if (id === undefined || id === "") throw new Error("open returned no id");
  return id;
}

test.describe("EDA data parts render in the thread", () => {
  test("an exploration turn draws the chips, the counts and the volcano", async ({
    page,
    context,
  }) => {
    const conversationId = await openConversation(context);

    const stream = [
      sseFrame({
        type: "start",
        messageId: "22222222-2222-2222-2222-222222222222",
        messageMetadata: {
          phase: "frame",
          model: "mock:deterministic",
          traceId: "mock-eda-trace",
          createdAt: new Date().toISOString(),
        },
      }),
      sseFrame({
        type: "data-eda.analysis-state",
        data: analysisState({
          revision: 1,
          numFilters: 1,
          filters: [FEBRILE_FILTER],
          filterSummaries: ["temperature_condition is febrile"],
        }),
      }),
      sseFrame({ type: "data-eda.subset-preview", data: SUBSET_PREVIEW }),
      sseFrame({ type: "data-eda.viz", data: VOLCANO_VIZ }),
      sseFrame({ type: "finish", finishReason: "stop" }),
      sseDone(),
    ].join("");

    await page.route("**/api/v1/chat", (route) =>
      route.fulfill({
        status: 200,
        headers: uiMessageStreamHeaders(),
        body: stream,
      }),
    );

    await page.goto(`/plasmodb/conversation/${conversationId}`);
    const composer = page.getByTestId("message-input");
    await expect(composer).toBeVisible({ timeout: 30_000 });
    await composer.click();
    await composer.pressSequentially("explore the heat shock study", { delay: 15 });
    await expect(page.getByRole("button", { name: /Send/i })).toBeEnabled({
      timeout: 15_000,
    });
    await composer.press("Enter");

    const card = page.getByTestId("data-eda-analysis-state");
    await expect(card).toBeVisible({ timeout: 20_000 });
    await expect(card).toContainText("Heat shock response in sensitive mutants");
    await expect(card).toContainText("6 of 12 Sample");
    await expect(page.getByTestId("data-eda-filter-chip-0")).toContainText(
      "temperature_condition is febrile",
    );

    const preview = page.getByTestId("data-eda-subset-preview");
    await expect(preview).toContainText("6 of 12 Sample");
    await expect(page.getByTestId("data-eda-subset-histogram")).toBeVisible();

    const volcano = page.getByTestId("eda-viz-volcano");
    await expect(volcano).toBeVisible();
    await expect(volcano.locator("canvas")).toBeVisible();
    await expect(page.getByTestId("eda-viz-volcano-selection")).toContainText(
      "1 gene selected",
    );
    await expect(page.getByTestId("eda-viz-volcano-dropped")).toContainText(
      "1 point without a p-value was not plotted",
    );
  });

  test("the rail marks the EDA panel and opens the tab", async ({ page, context }) => {
    const conversationId = await openConversation(context);
    const stream = [
      sseFrame({
        type: "start",
        messageId: "33333333-3333-3333-3333-333333333333",
        messageMetadata: {
          phase: "frame",
          model: "mock:deterministic",
          traceId: "mock-eda-trace-2",
          createdAt: new Date().toISOString(),
        },
      }),
      sseFrame({ type: "data-eda.analysis-state", data: analysisState() }),
      sseFrame({ type: "finish", finishReason: "stop" }),
      sseDone(),
    ].join("");
    await page.route("**/api/v1/chat", (route) =>
      route.fulfill({
        status: 200,
        headers: uiMessageStreamHeaders(),
        body: stream,
      }),
    );

    await page.goto(`/plasmodb/conversation/${conversationId}`);
    const composer = page.getByTestId("message-input");
    await expect(composer).toBeVisible({ timeout: 30_000 });
    await composer.click();
    await composer.pressSequentially("open the heat shock study", { delay: 15 });
    await composer.press("Enter");

    await expect(page.getByTestId("data-eda-analysis-state")).toBeVisible({
      timeout: 20_000,
    });
    await page.getByRole("button", { name: /^(Open|Close) EDA$/ }).click();
    // RightRail.tsx names its toggles "Open EDA"/"Close EDA", and it may
    // auto-open a panel - guard on visibility, not on a bare name.
    await expect(page.getByTestId("rail-eda-panel")).toContainText(
      "Heat shock response in sensitive mutants",
    );
    await page.getByTestId("rail-eda-open").click();
    await expect(page).toHaveURL(
      new RegExp(`/plasmodb/conversation/${conversationId}/eda$`),
    );
  });
});
```

`data-testid="message-input"` and the accessible `Send` button name are the
composer selectors `durable-verification.spec.ts` uses; the older
`message-composer` and `send-button` testids do not exist in the post-AI-SDK-v6
composer. `CSRF_HEADERS` comes from `apps/web/e2e/fixtures/api-client.ts`.

- [ ] **Run and read the failure.**
  `npx playwright test e2e/feature/eda-chat-parts.spec.ts`
  Record the first failure verbatim. Before it passes, the same wiring is
  already proven in jsdom by section A's renderer tests, which is why this spec
  is a confirmation and not the primary evidence.

- [ ] **Gates.** `node scripts/check-no-first-nth.mjs` then
  `npx playwright test e2e/feature/eda-chat-parts.spec.ts`.

### Task B3: journey 2, the co-edit loop

- [ ] **Failing test.** Create `apps/web/e2e/feature/eda-coedit.spec.ts`:

```ts
import { test, expect, BASE_URL } from "../fixtures/test";
import { sseDone, sseFrame, uiMessageStreamHeaders } from "../fixtures/sse";
import {
  analysisState,
  COUNTS_FEBRILE,
  FEBRILE_FILTER,
  routeEdaReads,
  STUDY_ROW,
} from "../fixtures/eda";
import { CSRF_HEADERS } from "../fixtures/api-client";
import type { BrowserContext } from "@playwright/test";

async function openConversation(context: BrowserContext): Promise<string> {
  const resp = await context.request.post(`${BASE_URL}/api/v1/conversations/open`, {
    data: { siteId: "plasmodb" },
    headers: CSRF_HEADERS,
  });
  const body = (await resp.json()) as { conversationId?: string; id?: string };
  const id = body.conversationId ?? body.id;
  if (id === undefined || id === "") throw new Error("open returned no id");
  return id;
}

test.describe("EDA tab and chat co-edit one analysis", () => {
  test("a filter added in the tab reaches the next analysis-state card", async ({
    page,
    context,
  }) => {
    const conversationId = await openConversation(context);
    await routeEdaReads(page);

    const patchActions: string[] = [];
    await page.route(`**/api/v1/conversations/${conversationId}/eda`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ analysis: null }),
        });
        return;
      }
      const body = route.request().postDataJSON() as { action: string };
      patchActions.push(body.action);
      const analysis =
        body.action === "bind"
          ? analysisState({ revision: 0 })
          : analysisState({
              revision: 1,
              numFilters: 1,
              filters: [FEBRILE_FILTER],
              filterSummaries: ["temperature_condition is febrile"],
              entityCounts: COUNTS_FEBRILE,
            });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ analysis, job: null, step: null }),
      });
    });

    await page.goto(`/plasmodb/conversation/${conversationId}/eda`);

    await page.getByTestId("eda-study-search").fill("heat shock");
    await page.getByTestId(`eda-study-row-${STUDY_ROW.datasetId}`).click();
    await expect(page.getByTestId("eda-subset-cell")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("eda-entity-ENT_8151325d")).toContainText(
      "12 of 12",
    );

    await page.getByTestId("eda-variable-VAR_081ab087").click();
    await page.getByRole("checkbox", { name: "febrile" }).check();
    await page.getByRole("button", { name: "Apply filter" }).click();

    await expect(page.getByTestId("eda-entity-ENT_8151325d")).toContainText("6 of 12");
    await expect(
      page.getByTestId("eda-filter-chip-ENT_8151325d-VAR_081ab087"),
    ).toContainText("febrile");
    expect(patchActions).toEqual(["bind", "set-filters"]);

    // The next turn re-states the same analysis, and the thread agrees with the tab.
    const stream = [
      sseFrame({
        type: "start",
        messageId: "44444444-4444-4444-4444-444444444444",
        messageMetadata: {
          phase: "frame",
          model: "mock:deterministic",
          traceId: "mock-eda-coedit",
          createdAt: new Date().toISOString(),
        },
      }),
      sseFrame({
        type: "data-eda.analysis-state",
        data: analysisState({
          revision: 2,
          numFilters: 1,
          filters: [FEBRILE_FILTER],
          filterSummaries: ["temperature_condition is febrile"],
          entityCounts: COUNTS_FEBRILE,
        }),
      }),
      sseFrame({ type: "finish", finishReason: "stop" }),
      sseDone(),
    ].join("");
    await page.route("**/api/v1/chat", (route) =>
      route.fulfill({
        status: 200,
        headers: uiMessageStreamHeaders(),
        body: stream,
      }),
    );

    await page.goto(`/plasmodb/conversation/${conversationId}`);
    const composer = page.getByTestId("message-input");
    await expect(composer).toBeVisible({ timeout: 30_000 });
    await composer.click();
    await composer.pressSequentially("what is in the subset now", { delay: 15 });
    await composer.press("Enter");

    await expect(page.getByTestId("data-eda-filter-chip-0")).toContainText(
      "temperature_condition is febrile",
      { timeout: 20_000 },
    );
    await expect(page.getByTestId("data-eda-analysis-state")).toContainText(
      "6 of 12 Sample",
    );
  });
});
```

- [ ] **Before writing the browser test**, confirm the loop is already proven in
  jsdom: batch 6 Task A5 asserts the PATCH body and the server echo clearing
  `localFilters`, and batch 5 Task B1 asserts the reconcile rule. If either is
  missing, stop and reopen that batch rather than compensating here.

- [ ] **Gates.** `node scripts/check-no-first-nth.mjs` then
  `npx playwright test e2e/feature/eda-coedit.spec.ts`.

### Task B4: journey 3, export as a step

- [ ] **Failing test.** Create `apps/web/e2e/feature/eda-export-step.spec.ts`.
  Bind the analysis, drive the compute cell with a routed `run-compute` response
  whose job status is `complete`, then click export and assert the strategy rail
  lists a step.

```ts
import { test, expect, BASE_URL } from "../fixtures/test";
import { analysisState, routeEdaReads, STUDY_ROW } from "../fixtures/eda";
import { CSRF_HEADERS } from "../fixtures/api-client";
import type { BrowserContext } from "@playwright/test";

async function openConversation(context: BrowserContext): Promise<string> {
  const resp = await context.request.post(`${BASE_URL}/api/v1/conversations/open`, {
    data: { siteId: "plasmodb" },
    headers: CSRF_HEADERS,
  });
  const body = (await resp.json()) as { conversationId?: string; id?: string };
  const id = body.conversationId ?? body.id;
  if (id === undefined || id === "") throw new Error("open returned no id");
  return id;
}

test.describe("EDA export as a strategy step", () => {
  test("a completed compute exports a step the strategy rail lists", async ({
    page,
    context,
  }) => {
    const conversationId = await openConversation(context);
    await routeEdaReads(page);

    await page.route(`**/api/v1/conversations/${conversationId}/eda`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ analysis: null }),
        });
        return;
      }
      const body = route.request().postDataJSON() as { action: string };
      if (body.action === "run-compute") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            analysis: analysisState({ revision: 1, numComputations: 1 }),
            job: {
              jobId: "db04204e5386396e1ca2cb78469ab6fb",
              taskId: null,
              appName: "differentialexpression",
              status: "complete",
            },
            step: null,
          }),
        });
        return;
      }
      if (body.action === "export-step") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            analysis: analysisState({ revision: 2, numComputations: 1 }),
            job: null,
            step: {
              id: conversationId,
              siteId: "plasmodb",
              recordType: "transcript",
              rootStepId: "step_eda_1",
              isSaved: false,
              steps: [
                {
                  id: "step_eda_1",
                  searchName: "GenesByEdaVizWithCompute",
                  displayName: "EDA volcano, 1543 genes",
                  estimatedSize: 1543,
                },
              ],
            },
          }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          analysis: analysisState({ revision: 0 }),
          job: null,
          step: null,
        }),
      });
    });

    await page.goto(`/plasmodb/conversation/${conversationId}/eda`);
    await page.getByTestId("eda-study-search").fill("heat shock");
    await page.getByTestId(`eda-study-row-${STUDY_ROW.datasetId}`).click();
    await expect(page.getByTestId("eda-compute-cell")).toBeVisible({ timeout: 20_000 });

    await page.getByLabel("Comparator variable").selectOption("VAR_081ab087");
    await page.getByLabel("Group A").selectOption("normal");
    await page.getByLabel("Group B").selectOption("febrile");
    await page.getByRole("button", { name: "Run compute" }).click();

    const exportButton = page.getByRole("button", { name: "Export as step" });
    await expect(exportButton).toBeEnabled({ timeout: 20_000 });
    await exportButton.click();

    await page.goto(`/plasmodb/conversation/${conversationId}`);
    await page.getByRole("button", { name: /^(Open|Close) Strategy$/ }).click();
    await expect(page.getByTestId("rail-strategy-panel")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("compact-step-row-step_eda_1")).toContainText(
      "EDA volcano",
    );
  });
});
```

`rail-strategy-panel` and `compact-step-row-<id>` are the existing strategy rail
testids, named in `apps/web/e2e/pages/graph.page.ts` lines 33-47.

The last navigation drops the in-memory strategy cache, so this assertion only
holds if the export PATCH also persisted the step server side. Read batch 3's
`create_eda_step` behavior first and record the decision in the task report. If
it does not persist, assert the rail **without** the reload (open the rail from
the tab's own route is not possible, so navigate back with client-side routing
by clicking the nav rail's Chat entry rather than `page.goto`, which keeps the
query cache alive) and note that batch 6 Task B4's jsdom test already asserts
the cache write.

- [ ] **Gates.** `node scripts/check-no-first-nth.mjs` then
  `npx playwright test e2e/feature/eda-export-step.spec.ts`.

### Task B5: closure, the edits to hand the session lead

Do **not** edit these files. List the exact edits in the task report; the
session lead applies them, because two of the three files are read by other
plan documents.

- [ ] **`docs/knowledge/eda/pathfinder-integration-concept.md`.** Report these
  three edits:
  1. Frontmatter: `status: draft` becomes `status: accepted`.
  2. Lines 13-15, currently
     "Status: proposal from the 2026-08-27 research pass. Nothing here is
     committed. The facts it stands on are in ...", become
     "Status: implemented by the EDA integration plan. The facts it stands on
     are in ...", where "the EDA integration plan" is a markdown link whose
     target is the relative path `plan/index.md`.
  3. Section "Seam 2: a workbench-style EDA tab (large)": the six bullets
     describe the tab in the conditional. Each becomes indicative and names its
     implementation, for example "Study picker over `/studies` ... searchable"
     becomes "Study picker over `/studies`, searchable, in
     `apps/web/src/features/eda/StudyPicker.tsx`". The visualization-cell bullet
     also gains the settled limit: the `data-eda.viz` part carries a point
     cloud, so volcano and scatter render and histogram, bar and boxplot do not.

- [ ] **`docs/knowledge/eda/pathfinder-architecture-fit.md`.** Report one edit:
  line 13, "Status: proposal. Nothing here is built.", becomes
  "Status: built. See the plan for the batches that built it.", where "the plan"
  is a markdown link whose target is the relative path `plan/index.md`; and the
  frontmatter `status: draft` becomes `status: accepted`.

- [ ] **`docs/knowledge/backlog/execute-eda-integration-plan.md`.** Report that
  the file is deleted, together with its line in
  `docs/knowledge/backlog/index.md`: currently line 93, a bullet whose link text
  is "Execute the EDA integration plan" and whose target is
  `execute-eda-integration-plan.md`. Items are removed when done, not marked
  done, and both edits land in the same change that finishes the last task.

- [ ] **`docs/knowledge/log.md`.** Report one line to append, naming the seven
  batches and the two surfaces, in the file's existing entry format. Read the
  file's last three entries first and match them.

- [ ] **`docs/knowledge/eda/plan/index.md` and the seven batch documents.**
  Report that each batch document's frontmatter `status: draft` becomes
  `status: accepted` once its verifier is accepted.

- [ ] **Report any residual contract question.** `BoxplotChart` was already
  removed from the contract at plan time (overview and batch 5 both say so);
  confirm no boxplot file crept back in, and report anything else that
  diverged from [overview.md](overview.md).

- [ ] **Verify the knowledge bundle** after the lead applies the edits:
  `node /Users/ahmedmuharram/repos/pathfinder/scripts/check-knowledge.mjs`.
  It fails on a dangling relative link, on a concept not linked from its
  directory index, on a missing `type` in frontmatter, and on any em dash, en
  dash, curly quote or unicode ellipsis in any `.md`.

### Task B6: the full ladder and the container check

- [ ] **Type generation freshness.** Batch 4 changed Pydantic schemas, so the
  generated TypeScript must be current:

```
cd /Users/ahmedmuharram/repos/pathfinder
yarn generate:types
git status --porcelain packages/shared-ts/src/generated packages/spec
```

A non-empty result means the committed generated output is stale. Report the
exact files; the session lead commits the regeneration in the same change.
Do not run any other git command.

- [ ] **Rebuild and confirm the containers actually updated.**

```
cd /Users/ahmedmuharram/repos/pathfinder
docker compose --env-file .env.dev up -d --build api worker web
docker compose ps
```

`up -d --build` can build a new image and leave the old container running, so
confirm the new code is inside the container before claiming anything works,
for example by grepping a symbol this plan added:

```
docker compose exec api grep -rl "conversation_analyses" /app/src/pathfinder/persistence
```

If it is absent, `docker compose --env-file .env.dev up -d --force-recreate api worker web`.

- [ ] **Backend suite on the host.** The api image ships no test tree, so
  the suite runs from the checkout:

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/api
uv run pytest src/pathfinder/tests/ -q
uv run ruff check src/
uv run mypy --strict src/pathfinder/
uv run pyright src/pathfinder/
```

- [ ] **Frontend ladder, complete.**

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
yarn format
npx tsc --noEmit
npx eslint src/
node scripts/check-boundaries.mjs
node scripts/check-weak-assertions.mjs
node scripts/check-no-first-nth.mjs
npx vitest run
npx playwright test e2e/feature/eda-chat-parts.spec.ts e2e/feature/eda-coedit.spec.ts e2e/feature/eda-export-step.spec.ts
```

- [ ] **Assistant packages, because `PROTOCOL.md` gates its consumer.**

```
cd /Users/ahmedmuharram/repos/pathfinder/packages/assistant-core && uv run pytest && uv run ruff check src/ tests/ && uv run mypy --strict src/
cd /Users/ahmedmuharram/repos/pathfinder/packages/assistant-client-ts && yarn test && yarn typecheck && yarn lint
```

If `PROTOCOL.md` gained the three `data-eda.*` kinds in batch 3 or 4, the
client's conformance suite must already be green; a red suite here means an
earlier batch left it red, and this batch does not paper over it.

- [ ] **Knowledge gate.**
  `node /Users/ahmedmuharram/repos/pathfinder/scripts/check-knowledge.mjs`

### Section B close-out

- [ ] Report: the three specs and their runtimes; the decision recorded in Task
  B4 about server-side step persistence; every stale generated file from Task
  B6; the exact closure edits from Task B5, ready to paste; zero-debt statement
  or the debt.

## Verifier

Re-run everything in Task B6 from a clean checkout, plus:

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
npx playwright test e2e/feature/eda-chat-parts.spec.ts --repeat-each 3
```

Three repeats, because zero tolerance for flaky tests: a flaky e2e is an app
bug, and the fix is in the app, not the test.

Read every created and modified file. Then hunt these traps by name:

1. **A `useEffect`**, or `useLayoutEffect` from `react`, anywhere in the diff.
2. **`useMemo`, `useCallback` or `memo`.**
3. **`.first(`, `.nth(` or `.last(` in a new spec.** The gate script catches it;
   a `TODO(weak-strict-mode)` marker added to pass the gate is a FAIL here
   unless the report justifies it against a real ambiguity.
4. **A `features/conversation` file importing `@/features/eda`**, or a new entry
   in `CROSS_FEATURE_EXCEPTIONS`.
5. **A filter summarised in the chat card.** The card must print
   `filterSummaries` verbatim; a `switch` over filter types inside
   `features/conversation` means the implementer duplicated the tab's helper.
6. **`filterSummary` moved out of `features/eda`** to serve the chat card.
7. **A production edit made by Implementer B.** Section B modifies nothing under
   `src/`.
8. **A new scripted turn or marker added to the backend mock.** The chat route
   is mocked in the browser; a backend mock change here means the implementer
   ignored the pattern the task card cites.
9. **A spec that reads a real chat tail on a thread it already answered with a
   mocked one.** Each test must open its own conversation.
10. **A spec asserting a chart by its container only.** The canvas assertion
    `volcano.locator("canvas")` is the point: it proves ECharts actually
    rendered.
11. **A count in an assertion that is not hand-computable from the fixture in
    the same file.** Every number must be traceable.
12. **A reconcile rule reimplemented in a renderer.** The renderers call
    `useHydrateEdaPart`; only `state/eda.ts` decides what supersedes what.
13. **A `chart` value drawn as something it is not.** `histogram`, `bar` and
    `boxplot` must render the named notice; drawing a volcano for them, or
    falling through to a default branch, is a FAIL.
14. **A `pointID`, a `Number.parseFloat` on a viz field, or a fabricated
    p-value floor** anywhere in the diff.
15. **`count` rendered without `unfilteredCount`** in either card.
16. **A rail edit left half done.** All four edits of Task A4 must be present:
    `RIGHT_RAIL_PANELS`, `LastSeen`, `railActivity`, and RightRail's
    `RAIL_ICONS`, `hasUpdate` and `markersFor`.
17. **A file over 300 eslint-counted lines**, or a silenced `max-lines`.
18. **A test whose only matchers are weak**, or a test asserting existence
    rather than a value.
19. **Smart punctuation** in any new source file or doc, and any em dash in a
    comment.
20. **A closure edit applied by the implementer** instead of reported, and any
    backlog file marked done rather than deleted.
21. **A stale generated type** left uncommitted after `yarn generate:types`.
22. **A container claimed updated without evidence.** The report must quote the
    `docker compose exec` grep that proved it.

Report format, mandatory:

```
Batch 7 verification

Gates
  tsc --noEmit                PASS/FAIL  <first error if FAIL>
  eslint src/                 PASS/FAIL  <count>
  check-boundaries.mjs        PASS/FAIL  <count>
  check-weak-assertions.mjs   PASS/FAIL  <count>
  check-no-first-nth.mjs      PASS/FAIL  <count>
  vitest run                  PASS/FAIL  <passed>/<total>
  playwright (3 eda specs)    PASS/FAIL  <passed>/<total>, <duration>
  playwright repeat-each 3    PASS/FAIL  <any flake>
  api pytest / ruff / mypy / pyright   PASS/FAIL each
  assistant-core / assistant-client-ts PASS/FAIL each
  check-knowledge.mjs         PASS/FAIL
  yarn generate:types clean   PASS/FAIL  <stale files>

Per task
  A1 DataEdaViz             PASS/FAIL  <evidence>
  A2 DataEdaAnalysisState   PASS/FAIL
  A3 DataEdaSubsetPreview   PASS/FAIL
  A4 rail entry             PASS/FAIL
  B1 e2e fixtures           PASS/FAIL
  B2 journey 1 chat-only    PASS/FAIL
  B3 journey 2 co-edit      PASS/FAIL
  B4 journey 3 export       PASS/FAIL
  B5 closure edits listed   PASS/FAIL
  B6 full ladder            PASS/FAIL

Traps  (1 to 22, each CLEAN or the file:line that violates it)

Definition of done
  zero debt            YES/NO  <what remains>
  adjacent reconciled  YES/NO  <what was missed>
  tests assert values  YES/NO
  backlog entry gone   YES/NO
```

## Exit criteria

For the session lead to close batch 7 and the plan:

1. Every gate in Task B6 green, verified by the lead's own run, with the
   Playwright specs green on three repeats.
2. The three `data-eda.*` parts render inline in the thread: the study title,
   the analysis name, the backend's `filterSummaries` as chips and every entity
   count as "count of unfilteredCount" on the analysis-state card; counts plus a
   mini histogram on the subset preview; a real `<canvas>` for `volcano` and
   `scatter`, and a named notice for `histogram`, `bar` and `boxplot`.
3. A chat-driven change moves the tab and a tab-driven change comes back on the
   agent's next analysis-state part, both proven by journey 2, with no
   conversation event written by the PATCH.
4. Export writes a step the strategy rail lists, proven by journey 3, with the
   persistence decision recorded.
5. The right-rail EDA panel exists, marks unseen EDA activity, names the study,
   the analysis, the filter count and the computation count, and opens the tab.
6. `features/conversation` still imports nothing from `features/eda`, and
   `CROSS_FEATURE_EXCEPTIONS` is unchanged across the whole plan.
7. The closure edits from Task B5 are applied by the lead:
   `pathfinder-integration-concept.md` and `pathfinder-architecture-fit.md`
   reconciled, `docs/knowledge/log.md` appended, every batch document's
   frontmatter `status: accepted`, and
   `docs/knowledge/backlog/execute-eda-integration-plan.md` deleted together
   with its line in `docs/knowledge/backlog/index.md`.
8. `node scripts/check-knowledge.mjs` green after those edits, and
   `docs/knowledge/backlog/` holds only what genuinely remains.
9. The verifier's report shows all twenty-two traps CLEAN, "zero debt YES" and
   "backlog entry gone YES".
