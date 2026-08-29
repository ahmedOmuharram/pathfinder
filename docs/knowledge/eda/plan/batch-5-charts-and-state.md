---
type: Plan
title: "Batch 5: charts and state"
description: The ECharts foundation in lib/components/charts, the useEdaStore analysis store, the lib/api/eda transport wrappers, and the store-hydration glue that turns batch 4's text-only EDA part renderers into live co-edit sources.
tags: [eda, pathfinder, plan, batch, frontend, charts, zustand, echarts]
generated: { by: claude-code/opus-5, at: 2026-08-28T00:00:00Z }
verified: { by: claude-code/fable-5, at: 2026-08-28T00:00:00Z }
status: accepted
---

# Batch 5: charts and state

**Goal:** build the pure chart foundation in `lib/` and the EDA client state
plus transport wrappers, so batches 6 and 7 can render the same plots and the
same analysis document in two surfaces from one code path.

**Prerequisites:** batch 4 closed. Batch 4 has already added
`data-eda.analysis-state`, `data-eda.subset-preview` and `data-eda.viz` to
`KnownDataPartKind` and `DataPartPayloadMap`, published their zod schemas under
`packages/shared-ts/src/generated/zod/`, shipped the `/api/v1/eda/*` router, and
**created the three text-only renderer files plus `content/edaDataParts.ts` and
their registration in `content/contentComponents.ts`**. `tsc` is green when this
batch opens; batch 4's exit criteria guarantee it.

**Read before starting:**

- [overview.md](overview.md) - the pinned shared contract. Names there are law.
- [../visualizations.md](../visualizations.md) - the upstream response shapes
  the backend normalizes, live-verified.
- [../subsetting-and-tabular.md](../subsetting-and-tabular.md) - distribution
  and count semantics.
- [../computes-and-jobs.md](../computes-and-jobs.md) - the six job states and
  the job id that is a hash of the request.
- [batch-6-eda-tab.md](batch-6-eda-tab.md) and
  [batch-7-chat-coediting-and-e2e.md](batch-7-chat-coediting-and-e2e.md) - what
  consumes what this batch produces.

## The settled contract this batch codes against

These are facts, not assumptions. They come from batch 3's shared models and
batch 4's router, and the session lead has reconciled them.

```ts
interface EdaEntityCount {
  entityId: string;
  entityDisplayName: string;
  count: number;
  unfilteredCount: number;
}

interface EdaDistributionSeries {
  variableId: string;
  variableDisplayName: string;
  labels: string[];
  values: number[];
  subsetSize: number;
  numVarValues: number;
  numMissingCases: number;
  isMultiValued: boolean;
}

// data-eda.analysis-state
interface EdaAnalysisState {
  siteId: string;
  datasetId: string;
  studyId: string;
  analysisId: string;
  revision: number | null;
  studyDisplayName: string;
  displayName: string;
  numFilters: number;
  numComputations: number;
  filters: unknown[];
  filterSummaries: string[];
  entityCounts: EdaEntityCount[];
  canExportRows: boolean;
}

// data-eda.subset-preview
interface EdaSubsetPreviewPart {
  datasetId: string;
  analysisId: string;
  entityCounts: EdaEntityCount[];
  distribution: EdaDistributionSeries | null;
}

// data-eda.viz
interface EdaVizPart {
  datasetId: string;
  analysisId: string;
  chart: "volcano" | "histogram" | "boxplot" | "bar" | "scatter";
  effectSizeLabel: string;
  effectSizeThreshold: number | null;
  significanceThreshold: number | null;
  effectDirection: "upOnly" | "downOnly" | "upAndDown" | null;
  totalPoints: number;
  retainedPoints: number;
  points: {
    pointId: string;
    effectSize: number;
    pValue?: number | null;
    adjustedPValue?: number | null;
    retained: boolean;
  }[];
}
```

Five consequences that shape every task below.

1. **`studyDisplayName` is the study title; `displayName` is the analysis's own
   name.** They are different strings and both are shown.
2. **`filters` is `unknown[]`.** The shared Python models cannot import the
   filter union, so the generated TypeScript types it as `unknown`. The store
   parses **each** entry with the generated `edaFilterSchema` through
   `safeParse` and drops failures, counting them. Editable chips in batch 6 read
   the parsed filters from the store; the chat card in batch 7 reads
   `filterSummaries`, which the backend already rendered.
3. **The viz part carries numbers, not strings, and `pointId` with a lowercase
   d.** Upstream sends every numeric field as a string and spells the field
   `pointID` ([../visualizations.md](../visualizations.md)); batch 3 normalizes
   both. So the chart components in this batch take **numbers**. `pValue` and
   `adjustedPValue` are optional **and** nullable: one live row of 5511 carried
   neither.
4. **The viz part carries a point cloud and nothing else.** There are no
   histogram bins, no bar labels, no boxplot fences and no PCA axes in it. So
   `chart: "volcano"` and `chart: "scatter"` are renderable from it and
   `histogram`, `bar` and `boxplot` are not. Batch 7 renders a named notice for
   those three rather than drawing a wrong chart.
5. **`effectDirection` is `upOnly | downOnly | upAndDown`.** The chart
   components use that exact vocabulary, so nothing translates it.

## Inherited constraints

Copied here so no implementer needs another file.

**TDD is non-negotiable.** No production code without a failing test first.
Red, green, refactor. "Just moving code" is not an exemption. Tests verify
correctness (real numbers, real field names), not existence.

**React rules, enforced by `eslint.config.cjs`:**

- `useEffect` is banned. `no-restricted-imports` refuses
  `import { useEffect } from "react"`. Replacements the codebase already uses:
  a TanStack Query `queryFn` for a one-shot side effect
  (`features/conversation/content/parts/DataBackgroundTaskStarted.tsx`), a
  render-time `setState` guarded by a comparison plus `queueMicrotask` for the
  cross-store write (`app/[siteId]/(app)/layout.tsx` lines 63-69 and
  `features/conversation/rail/RightRail.tsx` lines 61-69), and
  `useIsomorphicLayoutEffect` from `usehooks-ts` when a layout read is
  unavoidable (`lib/components/SetVenn.tsx`).
- `useMemo`, `useCallback` and `memo` are banned. React Compiler is on
  (`next.config.ts`: `reactCompiler: true`).
- Imperative DOM mounting uses a **ref callback that returns its teardown**.
  React 19 calls the returned function on unmount instead of calling the ref
  with `null`. `echarts.init`, `ResizeObserver` and `dispose` all live there.

**Other eslint rules that will fail a careless edit:**
`max-lines` 300 per file (blank lines and comments skipped),
`@typescript-eslint/strict-boolean-expressions`,
`@typescript-eslint/no-unnecessary-condition`,
`@typescript-eslint/switch-exhaustiveness-check`,
`consistent-type-imports` with inline type imports,
`no-console` except `warn` and `error`.

**tsconfig strictness:** `strict`, `noUncheckedIndexedAccess`,
`exactOptionalPropertyTypes`, `noPropertyAccessFromIndexSignature`. Indexing an
array or a `Record` yields `T | undefined`. An optional property cannot be
assigned `undefined` explicitly; omit the key with a conditional spread.

**No type suppressions.** No `as any`, `@ts-ignore`, `@ts-expect-error`,
`eslint-disable`. `as any` is also refused by
`scripts/check-boundaries.mjs` rule 2.

**No `import as`.** Never `import X as Y` or `from X import Y as Z`.

**Frontend boundaries** (`scripts/check-boundaries.mjs`): a file under
`src/features/<name>/` may import only relative paths inside its own feature,
`@/lib/...`, `@/state/...`, `@pathfinder/shared`,
`@pathfinder/assistant-client`, `@/components/ui/...`,
`@/components/ai-elements/...`, and third-party packages. `src/lib/` must not
import from `features`, `state` or `app`. Charts live in `lib/` precisely
because two features render them.

**API calls go through `lib/api/`.** A component never calls `fetch`.

**Only the LLM is mocked.** EDA payloads used in tests are recorded real
responses, normalized the way batch 3 normalizes them.

**Comments:** 1 to 3 lines maximum, simple present tense, one idea per
sentence. No narration of the next line. No history, no incident, no dates, no
names. Near zero new comments. No module docstring that tells a story.

**ASCII punctuation only**, in code strings and in prose. No em dash, no en
dash, no curly quotes, no unicode ellipsis. Use " - " and "...".

**Definition of done.** Gates green is not done. Done means: zero debt from
this task (no dead code, no unread arguments, no always-true guards, no
temporary instrumentation, no new TODOs), adjacent reconciliation (every detail
the change invalidates is fixed in the same task), tests assert the new
behavior, and the recap leads with remaining debt rather than successes.
"Flag for later" is banned inside a session.

**Gate ladder for every task in this batch:**

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
npx tsc --noEmit
npx eslint src/
node scripts/check-boundaries.mjs
node scripts/check-weak-assertions.mjs
npx vitest run <exact test files for this task>
```

At the end of a section, additionally:

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
yarn format
npx vitest run
```

`scripts/check-weak-assertions.mjs` fails a test whose only `expect` chains use
`toBeTruthy`, `toBeFalsy`, `toBeDefined`, `toBeUndefined`, `toBeNull`,
`toBeNaN` or `toBeInstanceOf`, and fails a test with no `expect` at all. Use
`toBe`, `toEqual`, `toHaveLength`, `toThrow`, `toContainText`,
`toBeInTheDocument` and friends.

## New dependency

This batch adds exactly one runtime dependency:

```
cd /Users/ahmedmuharram/repos/pathfinder/apps/web
yarn add echarts
```

Rules for it, all mandatory:

- Import **only** from `echarts/core`, `echarts/charts`, `echarts/components`
  and `echarts/renderers`, and only inside
  `src/lib/components/charts/echartsRegistry.ts`. A bare `import ... from
  "echarts"` pulls the whole library and is a task failure.
- `echarts-for-react` is **not** installed and must not be. It ships its own
  `componentDidUpdate` lifecycle and a `useEffect`-based hook, both of which
  contradict the React Compiler and no-`useEffect` rules. The wrapper in
  `EChart.tsx` is hand-rolled for that reason.
- The repository already carries `recharts` and `reaviz`. Neither is removed by
  this batch and neither is used by EDA: both are SVG-only and a volcano plot is
  thousands of points, which is a canvas job. Record this in the task report; do
  not migrate existing consumers.
- Record the exact resolved version from `yarn.lock` in the task report and use
  only APIs present in it.

## Implementer A: the chart foundation

Everything here is pure `lib/` code with no EDA transport knowledge and no
feature imports.

### Files

**Create**

- `apps/web/src/lib/components/charts/echartsRegistry.ts`
- `apps/web/src/lib/components/charts/chartTheme.ts`
- `apps/web/src/lib/components/charts/types.ts`
- `apps/web/src/lib/components/charts/EChart.tsx`
- `apps/web/src/lib/eda/volcanoSelection.ts`
- `apps/web/src/lib/components/charts/volcano.options.ts`
- `apps/web/src/lib/components/charts/VolcanoChart.tsx`
- `apps/web/src/lib/components/charts/category.options.ts`
- `apps/web/src/lib/components/charts/HistogramChart.tsx`
- `apps/web/src/lib/components/charts/BarChart.tsx`
- `apps/web/src/lib/components/charts/scatter.options.ts`
- `apps/web/src/lib/components/charts/ScatterChart.tsx`

**Test**

- `apps/web/src/lib/components/charts/chartTheme.test.ts`
- `apps/web/src/lib/components/charts/EChart.test.tsx`
- `apps/web/src/lib/eda/volcanoSelection.test.ts`
- `apps/web/src/lib/components/charts/volcano.options.test.ts`
- `apps/web/src/lib/components/charts/VolcanoChart.test.tsx`
- `apps/web/src/lib/components/charts/category.options.test.ts`
- `apps/web/src/lib/components/charts/scatter.options.test.ts`

**Modify**

- `apps/web/package.json` and `apps/web/yarn.lock` (the `echarts` dependency).

### Interfaces

**Consumes:** nothing from batches 1 to 4. This section is deliberately
independent of the generated payload types: it takes the narrow row shapes the
payloads embed, so a field added to a part cannot break a chart.

**Produces**, all imported by batches 6 and 7 exactly as named:

```ts
// lib/components/charts/types.ts

/** One gene of a differential expression result, as the part carries it. */
export interface VolcanoPointInput {
  pointId: string;
  effectSize: number;
  pValue?: number | null;
  adjustedPValue?: number | null;
}

export type VolcanoDirection = "upOnly" | "downOnly" | "upAndDown";
export type VolcanoSignificanceField = "adjustedPValue" | "pValue";

export interface VolcanoThresholds {
  effectSizeThreshold: number;
  significanceThreshold: number;
  direction: VolcanoDirection;
}

/** Parallel label and value arrays, the shape both EDA distributions and EDA
 * barplots arrive in. */
export interface EdaCategorySeries {
  name: string;
  labels: string[];
  values: number[];
}

export interface EdaScatterSeries {
  name: string;
  x: number[];
  y: number[];
  pointIds?: string[];
}

export interface EdaAxisLabel {
  variableId: string;
  displayName: string;
}
```

```ts
// lib/eda/volcanoSelection.ts
export interface VolcanoSelection {
  up: string[];
  down: string[];
  selected: string[];
  droppedRowCount: number;
}
export function selectVolcanoGenes(
  points: readonly VolcanoPointInput[],
  thresholds: VolcanoThresholds,
  significanceField: VolcanoSignificanceField,
): VolcanoSelection;
export const VOLCANO_POINT_SAMPLE: readonly VolcanoPointInput[];
// Ordering contract: selected is up-then-down, each side in input order.
```

```ts
// lib/components/charts/EChart.tsx
export interface EChartProps {
  option: EChartsOption;
  height: number;
  ariaLabel: string;
  testId: string;
}
export function EChart(props: EChartProps): ReactElement;
```

Chart component props:

```ts
export interface VolcanoChartProps {
  points: readonly VolcanoPointInput[];
  thresholds: VolcanoThresholds;
  significanceField: VolcanoSignificanceField;
  effectSizeLabel: string;
  height: number;
  testId: string;
}
export interface HistogramChartProps {
  series: readonly EdaCategorySeries[];
  barMode: "overlay" | "stack";
  valueLabel: string;
  height: number;
  testId: string;
}
export interface BarChartProps {
  series: readonly EdaCategorySeries[];
  barMode: "group" | "stack";
  valueLabel: string;
  height: number;
  testId: string;
}
export interface ScatterChartProps {
  series: readonly EdaScatterSeries[];
  xAxis: EdaAxisLabel;
  yAxis: EdaAxisLabel;
  height: number;
  testId: string;
}
```

There is no `pValueFloor` prop. The viz part does not carry a floor, and
inventing the upstream default would put a fabricated number on a scientist's
axis. A point whose p-value is zero, null or absent is dropped and counted
instead.

### Consumers of each component, stated up front

A component with no consumer is debt, so this is settled before any code is
written:

| Component | Consumer |
|---|---|
| `VolcanoChart` | batch 6 `VizCell` for `chart: "volcano"`, batch 7 `DataEdaViz` |
| `ScatterChart` | batch 6 `VizCell` for `chart: "scatter"`, batch 7 `DataEdaViz` |
| `HistogramChart` | batch 6 `SubsetCell` sparkline for a **continuous** variable, batch 7 `DataEdaSubsetPreview` |
| `BarChart` | batch 6 `SubsetCell` sparkline for a **categorical, ordinal or binary** variable |
| `BoxplotChart` | **removed from the contract** by the session lead: the settled payloads carry no boxplot statistics and nothing consumes it. It returns with the first payload that carries fences. Do not build it. |

### Before the first task: load the dataviz skill

Run the `dataviz` skill (Skill tool, name `dataviz`) and read it before writing
any option builder or any color. It owns the form heuristic, the color formula
and validator, the mark specs, and the axis, legend and tooltip rules. Follow
it for every palette, axis and tooltip decision in this section. Its form
heuristic is also why `HistogramChart` and `BarChart` are two components over
one builder: a continuous distribution gets adjacent bars, a categorical one
gets separated bars.

The tokens exist already in `apps/web/src/styles/globals.css`:

```
--chart-1: 215 70% 50%    --chart-4: 0 72% 51%
--chart-2: 160 60% 45%    --chart-5: 270 60% 55%
--chart-3: 38 92% 50%     --chart-6: 190 70% 50%
--chart-positive: 160 60% 45%
--chart-negative: 0 72% 51%
--foreground  --muted-foreground  --border  --card  --background
```

They are bare HSL triples, so a consumer wraps them: `hsl(215 70% 50%)`. Dark
mode is the `.dark` class on the document element, which redefines the same
custom properties, so reading them at mount is theme correct with no media
query. The precedent for reading them from JavaScript is
`resolveChartColors()` in `apps/web/src/lib/components/SetVenn.tsx` lines
17-23.

### Task A1: the chart theme is built from the app's own tokens

- [ ] **Failing test.** Create
  `apps/web/src/lib/components/charts/chartTheme.test.ts`:

```ts
/**
 * @vitest-environment jsdom
 */
import { describe, expect, it } from "vitest";

import { buildChartTheme, readChartTokens, CHART_TOKEN_FALLBACKS } from "./chartTheme";

describe("readChartTokens", () => {
  it("falls back to the pinned palette when the document defines no tokens", () => {
    const tokens = readChartTokens();
    expect(tokens.series).toEqual(CHART_TOKEN_FALLBACKS.series);
    expect(tokens.positive).toBe(CHART_TOKEN_FALLBACKS.positive);
  });

  it("wraps a bare HSL triple from the document in hsl()", () => {
    document.documentElement.style.setProperty("--chart-positive", "160 60% 45%");
    const tokens = readChartTokens();
    expect(tokens.positive).toBe("hsl(160 60% 45%)");
    document.documentElement.style.removeProperty("--chart-positive");
  });
});

describe("buildChartTheme", () => {
  it("names the six series colors in token order", () => {
    const theme = buildChartTheme(CHART_TOKEN_FALLBACKS);
    expect(theme.color).toEqual(CHART_TOKEN_FALLBACKS.series);
  });

  it("paints axis text with the muted foreground and gridlines with the border", () => {
    const theme = buildChartTheme(CHART_TOKEN_FALLBACKS);
    expect(theme.textStyle.color).toBe(CHART_TOKEN_FALLBACKS.foreground);
    expect(theme.valueAxis.axisLabel.color).toBe(CHART_TOKEN_FALLBACKS.mutedForeground);
    expect(theme.valueAxis.splitLine.lineStyle.color).toBe(CHART_TOKEN_FALLBACKS.border);
  });

  it("gives the tooltip the card background and a border", () => {
    const theme = buildChartTheme(CHART_TOKEN_FALLBACKS);
    expect(theme.tooltip.backgroundColor).toBe(CHART_TOKEN_FALLBACKS.card);
    expect(theme.tooltip.borderColor).toBe(CHART_TOKEN_FALLBACKS.border);
  });
});
```

- [ ] **Run and read the failure.**
  `npx vitest run src/lib/components/charts/chartTheme.test.ts`
  Expected: `Failed to resolve import "./chartTheme"`.

- [ ] **Implement** `apps/web/src/lib/components/charts/chartTheme.ts`:

```ts
export interface ChartTokens {
  series: string[];
  positive: string;
  negative: string;
  foreground: string;
  mutedForeground: string;
  border: string;
  card: string;
  background: string;
}

export const CHART_TOKEN_FALLBACKS: ChartTokens = {
  series: [
    "hsl(215 70% 50%)",
    "hsl(160 60% 45%)",
    "hsl(38 92% 50%)",
    "hsl(0 72% 51%)",
    "hsl(270 60% 55%)",
    "hsl(190 70% 50%)",
  ],
  positive: "hsl(160 60% 45%)",
  negative: "hsl(0 72% 51%)",
  foreground: "hsl(222 47% 11%)",
  mutedForeground: "hsl(215 16% 40%)",
  border: "hsl(200 20% 89%)",
  card: "hsl(0 0% 100%)",
  background: "hsl(200 20% 97%)",
};

const SERIES_VARS = [
  "--chart-1",
  "--chart-2",
  "--chart-3",
  "--chart-4",
  "--chart-5",
  "--chart-6",
];

function resolve(
  style: CSSStyleDeclaration | null,
  variable: string,
  fallback: string,
): string {
  if (style === null) return fallback;
  const raw = style.getPropertyValue(variable).trim();
  return raw === "" ? fallback : `hsl(${raw})`;
}

export function readChartTokens(): ChartTokens {
  const style =
    typeof document === "undefined" ? null : getComputedStyle(document.documentElement);
  return {
    series: SERIES_VARS.map((v, i) =>
      resolve(style, v, CHART_TOKEN_FALLBACKS.series[i] ?? "hsl(215 70% 50%)"),
    ),
    positive: resolve(style, "--chart-positive", CHART_TOKEN_FALLBACKS.positive),
    negative: resolve(style, "--chart-negative", CHART_TOKEN_FALLBACKS.negative),
    foreground: resolve(style, "--foreground", CHART_TOKEN_FALLBACKS.foreground),
    mutedForeground: resolve(
      style,
      "--muted-foreground",
      CHART_TOKEN_FALLBACKS.mutedForeground,
    ),
    border: resolve(style, "--border", CHART_TOKEN_FALLBACKS.border),
    card: resolve(style, "--card", CHART_TOKEN_FALLBACKS.card),
    background: resolve(style, "--background", CHART_TOKEN_FALLBACKS.background),
  };
}

export interface ChartTheme {
  color: string[];
  backgroundColor: string;
  textStyle: { color: string; fontFamily: string; fontSize: number };
  valueAxis: {
    axisLine: { lineStyle: { color: string } };
    axisLabel: { color: string };
    splitLine: { lineStyle: { color: string } };
  };
  categoryAxis: {
    axisLine: { lineStyle: { color: string } };
    axisLabel: { color: string };
    splitLine: { show: boolean };
  };
  tooltip: {
    backgroundColor: string;
    borderColor: string;
    textStyle: { color: string; fontSize: number };
  };
  legend: { textStyle: { color: string } };
}

export function buildChartTheme(tokens: ChartTokens): ChartTheme {
  return {
    color: tokens.series,
    backgroundColor: "transparent",
    textStyle: {
      color: tokens.foreground,
      fontFamily: "var(--font-sans)",
      fontSize: 11,
    },
    valueAxis: {
      axisLine: { lineStyle: { color: tokens.border } },
      axisLabel: { color: tokens.mutedForeground },
      splitLine: { lineStyle: { color: tokens.border } },
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: tokens.border } },
      axisLabel: { color: tokens.mutedForeground },
      splitLine: { show: false },
    },
    tooltip: {
      backgroundColor: tokens.card,
      borderColor: tokens.border,
      textStyle: { color: tokens.foreground, fontSize: 11 },
    },
    legend: { textStyle: { color: tokens.mutedForeground } },
  };
}
```

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/lib/components/charts/chartTheme.test.ts`.

### Task A2: the tree-shaken registry

- [ ] **No test of its own, by design.** A unit test for a registration side
  effect would restate the import list. The registry is proven by Task A3, whose
  test mocks it, and by the batch-7 e2e, which asserts a real `<canvas>`. Write
  the file, prove it with `npx tsc --noEmit`, and record the decision in the
  task report.

- [ ] **Implement** `apps/web/src/lib/components/charts/echartsRegistry.ts`:

```ts
import { BarChart, LineChart, ScatterChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import { init, use } from "echarts/core";
import type { EChartsType } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";

import { buildChartTheme, readChartTokens } from "./chartTheme";

use([
  BarChart,
  LineChart,
  ScatterChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  CanvasRenderer,
]);

export function initChart(node: HTMLElement): EChartsType {
  return init(node, buildChartTheme(readChartTokens()), { renderer: "canvas" });
}
```

`LineChart` is registered because `MarkLineComponent` needs a line-capable
series for the volcano threshold guides. `DataZoomComponent` is registered so
the volcano can be zoomed; the volcano option enables it.

- [ ] **Gates.** `npx tsc --noEmit && npx eslint src/ && node scripts/check-boundaries.mjs`.

### Task A3: EChart mounts once, resizes, and disposes

The wrapper's whole job is lifecycle. Test the lifecycle, not the pixels.

- [ ] **Failing test.** Create
  `apps/web/src/lib/components/charts/EChart.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

const chartDouble = {
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
  isDisposed: vi.fn(() => false),
};
const initChart = vi.fn(() => chartDouble);

vi.mock("./echartsRegistry", () => ({ initChart }));

import { EChart } from "./EChart";

const observed: Element[] = [];
class ObserverDouble {
  constructor(private callback: () => void) {}
  observe(target: Element) {
    observed.push(target);
    this.callback();
  }
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  initChart.mockClear();
  chartDouble.setOption.mockClear();
  chartDouble.resize.mockClear();
  chartDouble.dispose.mockClear();
  observed.length = 0;
  vi.stubGlobal("ResizeObserver", ObserverDouble);
});

const flush = () => new Promise<void>((resolve) => queueMicrotask(resolve));

describe("EChart", () => {
  it("renders an accessible sized container", () => {
    const { getByTestId } = render(
      <EChart
        option={{ series: [] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    const node = getByTestId("chart-under-test");
    expect(node).toHaveAttribute("role", "img");
    expect(node).toHaveAttribute("aria-label", "Volcano plot");
    expect(node).toHaveStyle({ height: "240px" });
  });

  it("initialises exactly one instance and applies the option once", async () => {
    render(
      <EChart
        option={{ series: [] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    await flush();
    expect(initChart).toHaveBeenCalledTimes(1);
    expect(chartDouble.setOption).toHaveBeenCalledTimes(1);
  });

  it("observes its own node and resizes the instance", async () => {
    const { getByTestId } = render(
      <EChart
        option={{ series: [] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    await flush();
    expect(observed).toEqual([getByTestId("chart-under-test")]);
    expect(chartDouble.resize).toHaveBeenCalledTimes(1);
  });

  it("re-applies the option when a new option arrives, without re-initialising", async () => {
    const { rerender } = render(
      <EChart
        option={{ series: [] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    await flush();
    rerender(
      <EChart
        option={{ series: [{ type: "scatter", data: [] }] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    await flush();
    expect(initChart).toHaveBeenCalledTimes(1);
    expect(chartDouble.setOption).toHaveBeenCalledTimes(2);
  });

  it("disposes the instance on unmount", async () => {
    const { unmount } = render(
      <EChart
        option={{ series: [] }}
        height={240}
        ariaLabel="Volcano plot"
        testId="chart-under-test"
      />,
    );
    await flush();
    unmount();
    expect(chartDouble.dispose).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Run and read the failure.**
  `npx vitest run src/lib/components/charts/EChart.test.tsx`
  Expected: `Failed to resolve import "./EChart"`.

- [ ] **Implement** `apps/web/src/lib/components/charts/EChart.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { EChartsType } from "echarts/core";
import type { EChartsOption } from "echarts";

import { initChart } from "./echartsRegistry";

export interface EChartProps {
  option: EChartsOption;
  height: number;
  ariaLabel: string;
  testId: string;
}

export function EChart({ option, height, ariaLabel, testId }: EChartProps) {
  const [instance, setInstance] = useState<EChartsType | null>(null);
  const [applied, setApplied] = useState<EChartsOption | null>(null);

  // The ref callback closes over setters only, so its identity is stable and
  // React never re-attaches it.
  const [mount] = useState(
    () => (node: HTMLDivElement | null) => {
      if (node === null) return undefined;
      const chart = initChart(node);
      setInstance(chart);
      const observer = new ResizeObserver(() => {
        if (!chart.isDisposed()) chart.resize();
      });
      observer.observe(node);
      return () => {
        observer.disconnect();
        chart.dispose();
        setInstance(null);
        setApplied(null);
      };
    },
  );

  if (instance !== null && applied !== option) {
    setApplied(option);
    queueMicrotask(() => {
      if (!instance.isDisposed()) instance.setOption(option, { notMerge: true });
    });
  }

  return (
    <div
      ref={mount}
      data-testid={testId}
      role="img"
      aria-label={ariaLabel}
      style={{ height }}
      className="w-full"
    />
  );
}
```

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/lib/components/charts/EChart.test.tsx`.

### Task A4: volcano selection is exact and drops points without a p-value

The measured facts this task encodes: one live row of 5511 carried neither
`pValue` nor `adjustedPValue`, so both are optional and nullable; thresholds are
applied by the consumer because the upstream volcanoplot `config` is an object
with no properties allowed; `effectSizeThreshold: 1` plus
`significanceThreshold: 0.05` on the full live response selected 1543 genes, 529
up and 1014 down ([../visualizations.md](../visualizations.md)).

- [ ] **Failing test.** Create `apps/web/src/lib/eda/volcanoSelection.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { selectVolcanoGenes, VOLCANO_POINT_SAMPLE } from "./volcanoSelection";

const thresholds = {
  effectSizeThreshold: 1,
  significanceThreshold: 0.05,
  direction: "upAndDown" as const,
};

describe("selectVolcanoGenes", () => {
  it("splits the recorded sample into one up and one down gene", () => {
    const result = selectVolcanoGenes(
      VOLCANO_POINT_SAMPLE,
      thresholds,
      "adjustedPValue",
    );
    expect(result.up).toEqual(["PF3D7_0100200"]);
    expect(result.down).toEqual(["PF3D7_0100300"]);
    expect(result.selected).toEqual(["PF3D7_0100200", "PF3D7_0100300"]);
  });

  it("agrees with the retained flag the backend computed at the same thresholds", () => {
    const result = selectVolcanoGenes(
      VOLCANO_POINT_SAMPLE,
      thresholds,
      "adjustedPValue",
    );
    const serverRetained = VOLCANO_POINT_SAMPLE.filter((p) => p.retained).map(
      (p) => p.pointId,
    );
    expect([...result.selected].sort()).toEqual([...serverRetained].sort());
  });

  it("drops the point that carries no p-value and counts it", () => {
    const result = selectVolcanoGenes(
      VOLCANO_POINT_SAMPLE,
      thresholds,
      "adjustedPValue",
    );
    expect(result.droppedRowCount).toBe(1);
    expect(result.selected).not.toContain("PF3D7_MIT04200");
  });

  it("drops a point whose p-value is explicitly null", () => {
    const result = selectVolcanoGenes(
      [{ pointId: "NULLP", effectSize: 4, adjustedPValue: null, retained: false }],
      thresholds,
      "adjustedPValue",
    );
    expect(result.droppedRowCount).toBe(1);
    expect(result.selected).toEqual([]);
  });

  it("honours direction upOnly", () => {
    const result = selectVolcanoGenes(
      VOLCANO_POINT_SAMPLE,
      { ...thresholds, direction: "upOnly" },
      "adjustedPValue",
    );
    expect(result.selected).toEqual(["PF3D7_0100200"]);
  });

  it("honours direction downOnly", () => {
    const result = selectVolcanoGenes(
      VOLCANO_POINT_SAMPLE,
      { ...thresholds, direction: "downOnly" },
      "adjustedPValue",
    );
    expect(result.selected).toEqual(["PF3D7_0100300"]);
  });

  it("selects on the raw p-value when asked, which admits a third gene", () => {
    const result = selectVolcanoGenes(
      VOLCANO_POINT_SAMPLE,
      {
        effectSizeThreshold: 1,
        significanceThreshold: 0.3,
        direction: "upAndDown",
      },
      "pValue",
    );
    expect(result.up).toEqual(["PF3D7_0100200", "PF3D7_0100500"]);
    expect(result.down).toEqual(["PF3D7_0100300"]);
  });

  it("treats the effect-size threshold as inclusive on the absolute value", () => {
    const result = selectVolcanoGenes(
      [
        { pointId: "EXACT", effectSize: 1, adjustedPValue: 0.01, retained: true },
        { pointId: "UNDER", effectSize: 0.999, adjustedPValue: 0.01, retained: false },
      ],
      thresholds,
      "adjustedPValue",
    );
    expect(result.selected).toEqual(["EXACT"]);
  });
});
```

The raw-p-value case is hand-computed: at `significanceThreshold: 0.3` on
`pValue`, `PF3D7_0100500` (`effectSize: 1.2`, `pValue: 0.2`) also qualifies and
sorts into `up`; `PF3D7_0100100` still fails the effect-size gate.

- [ ] **Run and read the failure.**
  `npx vitest run src/lib/eda/volcanoSelection.test.ts`
  Expected: `Failed to resolve import "./volcanoSelection"`.

- [ ] **Implement** `apps/web/src/lib/eda/volcanoSelection.ts`:

```ts
import type {
  VolcanoPointInput,
  VolcanoSignificanceField,
  VolcanoThresholds,
} from "@/lib/components/charts/types";

/** One point per gene, from a recorded differentialexpression result. The
 * retained flag is the backend's answer at 1 and 0.05 on the adjusted p-value. */
export const VOLCANO_POINT_SAMPLE: readonly (VolcanoPointInput & {
  retained: boolean;
})[] = [
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
  {
    pointId: "PF3D7_0100400",
    effectSize: 0.4,
    pValue: 0.0001,
    adjustedPValue: 0.0009,
    retained: false,
  },
  {
    pointId: "PF3D7_0100500",
    effectSize: 1.2,
    pValue: 0.2,
    adjustedPValue: 0.4,
    retained: false,
  },
  { pointId: "PF3D7_MIT04200", effectSize: -1.49447459261845, retained: false },
];

export interface VolcanoSelection {
  up: string[];
  down: string[];
  selected: string[];
  droppedRowCount: number;
}

function finite(raw: number | null | undefined): number | null {
  if (raw === null || raw === undefined) return null;
  return Number.isFinite(raw) ? raw : null;
}

export function selectVolcanoGenes(
  points: readonly VolcanoPointInput[],
  thresholds: VolcanoThresholds,
  significanceField: VolcanoSignificanceField,
): VolcanoSelection {
  const up: string[] = [];
  const down: string[] = [];
  let droppedRowCount = 0;

  for (const point of points) {
    const effect = finite(point.effectSize);
    const significance = finite(point[significanceField]);
    if (effect === null || significance === null) {
      droppedRowCount += 1;
      continue;
    }
    if (Math.abs(effect) < thresholds.effectSizeThreshold) continue;
    if (significance >= thresholds.significanceThreshold) continue;
    if (effect > 0) up.push(point.pointId);
    else down.push(point.pointId);
  }

  const selected =
    thresholds.direction === "upOnly"
      ? [...up]
      : thresholds.direction === "downOnly"
        ? [...down]
        : [...up, ...down];
  return { up, down, selected, droppedRowCount };
}
```

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/lib/eda/volcanoSelection.test.ts`.

### Task A5: the volcano option

- [ ] **Failing test.** Create
  `apps/web/src/lib/components/charts/volcano.options.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { CHART_TOKEN_FALLBACKS } from "./chartTheme";
import { buildVolcanoOption, volcanoPointY } from "./volcano.options";
import { VOLCANO_POINT_SAMPLE } from "@/lib/eda/volcanoSelection";

const args = {
  points: VOLCANO_POINT_SAMPLE,
  thresholds: {
    effectSizeThreshold: 1,
    significanceThreshold: 0.05,
    direction: "upAndDown" as const,
  },
  significanceField: "adjustedPValue" as const,
  effectSizeLabel: "log2(Fold Change)",
  tokens: CHART_TOKEN_FALLBACKS,
};

describe("volcanoPointY", () => {
  it("is the negative base-ten log of the raw p-value", () => {
    expect(volcanoPointY(0.001)).toBeCloseTo(3, 12);
  });

  it("returns null for a zero p-value rather than Infinity", () => {
    expect(volcanoPointY(0)).toBe(null);
  });

  it("returns null when there is no p-value", () => {
    expect(volcanoPointY(undefined)).toBe(null);
  });

  it("returns null for an explicit null p-value", () => {
    expect(volcanoPointY(null)).toBe(null);
  });
});

describe("buildVolcanoOption", () => {
  it("plots three series: not-notable, up and down", () => {
    const option = buildVolcanoOption(args);
    expect(option.series.map((s) => s.name)).toEqual([
      "Not notable",
      "Higher in group B",
      "Higher in group A",
    ]);
  });

  it("puts each qualifying gene in its own series with the right point count", () => {
    const option = buildVolcanoOption(args);
    expect(option.series[0]?.data).toHaveLength(3);
    expect(option.series[1]?.data).toHaveLength(1);
    expect(option.series[2]?.data).toHaveLength(1);
  });

  it("carries the gene id on the point so the tooltip can name it", () => {
    const option = buildVolcanoOption(args);
    expect(option.series[1]?.data[0]?.[2]).toBe("PF3D7_0100200");
  });

  it("colors up with the positive token and down with the negative token", () => {
    const option = buildVolcanoOption(args);
    expect(option.series[1]?.itemStyle.color).toBe(CHART_TOKEN_FALLBACKS.positive);
    expect(option.series[2]?.itemStyle.color).toBe(CHART_TOKEN_FALLBACKS.negative);
  });

  it("draws three threshold guides: two effect-size and one significance", () => {
    const option = buildVolcanoOption(args);
    expect(option.thresholdLines).toEqual([
      { axis: "x", value: -1 },
      { axis: "x", value: 1 },
      { axis: "y", value: -Math.log10(0.05) },
    ]);
  });

  it("names the effect-size axis from the payload label", () => {
    const option = buildVolcanoOption(args);
    expect(option.xAxis.name).toBe("log2(Fold Change)");
  });

  it("reports the point it could not plot", () => {
    const option = buildVolcanoOption(args);
    expect(option.droppedRowCount).toBe(1);
  });
});
```

- [ ] **Run and read the failure.**
  `npx vitest run src/lib/components/charts/volcano.options.test.ts`
  Expected: `Failed to resolve import "./volcano.options"`.

- [ ] **Implement** `apps/web/src/lib/components/charts/volcano.options.ts`.
  The builder returns a narrow, fully typed structure rather than
  `EChartsOption`, so the test can assert on it; `VolcanoChart` composes the
  ECharts option from it.

```ts
import type { ChartTokens } from "./chartTheme";
import { selectVolcanoGenes } from "@/lib/eda/volcanoSelection";
import type {
  VolcanoPointInput,
  VolcanoSignificanceField,
  VolcanoThresholds,
} from "./types";

export type VolcanoPoint = [number, number, string];

export interface VolcanoSeries {
  name: string;
  data: VolcanoPoint[];
  itemStyle: { color: string; opacity: number };
}

export interface VolcanoThresholdLine {
  axis: "x" | "y";
  value: number;
}

export interface VolcanoOptionModel {
  series: VolcanoSeries[];
  thresholdLines: VolcanoThresholdLine[];
  xAxis: { name: string };
  yAxis: { name: string };
  droppedRowCount: number;
}

export interface BuildVolcanoOptionArgs {
  points: readonly VolcanoPointInput[];
  thresholds: VolcanoThresholds;
  significanceField: VolcanoSignificanceField;
  effectSizeLabel: string;
  tokens: ChartTokens;
}

export function volcanoPointY(pValue: number | null | undefined): number | null {
  if (pValue === null || pValue === undefined) return null;
  if (!Number.isFinite(pValue) || pValue <= 0) return null;
  return -Math.log10(pValue);
}

export function buildVolcanoOption(
  args: BuildVolcanoOptionArgs,
): VolcanoOptionModel {
  const selection = selectVolcanoGenes(
    args.points,
    args.thresholds,
    args.significanceField,
  );
  const upIds = new Set(selection.up);
  const downIds = new Set(selection.down);

  const neutral: VolcanoPoint[] = [];
  const up: VolcanoPoint[] = [];
  const down: VolcanoPoint[] = [];
  let droppedRowCount = 0;

  for (const point of args.points) {
    const y = volcanoPointY(point.pValue);
    if (!Number.isFinite(point.effectSize) || y === null) {
      droppedRowCount += 1;
      continue;
    }
    const plotted: VolcanoPoint = [point.effectSize, y, point.pointId];
    if (upIds.has(point.pointId)) up.push(plotted);
    else if (downIds.has(point.pointId)) down.push(plotted);
    else neutral.push(plotted);
  }

  return {
    series: [
      {
        name: "Not notable",
        data: neutral,
        itemStyle: { color: args.tokens.mutedForeground, opacity: 0.35 },
      },
      {
        name: "Higher in group B",
        data: up,
        itemStyle: { color: args.tokens.positive, opacity: 0.85 },
      },
      {
        name: "Higher in group A",
        data: down,
        itemStyle: { color: args.tokens.negative, opacity: 0.85 },
      },
    ],
    thresholdLines: [
      { axis: "x", value: -args.thresholds.effectSizeThreshold },
      { axis: "x", value: args.thresholds.effectSizeThreshold },
      { axis: "y", value: -Math.log10(args.thresholds.significanceThreshold) },
    ],
    xAxis: { name: args.effectSizeLabel },
    yAxis: { name: "-log10(p-value)" },
    droppedRowCount,
  };
}
```

`droppedRowCount` is recomputed here rather than reused from
`selectVolcanoGenes`: the selection drops a point with no `adjustedPValue`, the
plot drops a point with no plottable `pValue`, and those are different
questions. For the recorded sample both are 1.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/lib/components/charts/volcano.options.test.ts`.

### Task A6: VolcanoChart

- [ ] **Failing test.** Create
  `apps/web/src/lib/components/charts/VolcanoChart.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

const setOption = vi.fn();
vi.mock("./echartsRegistry", () => ({
  initChart: () => ({
    setOption,
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
  }),
}));

import { VolcanoChart } from "./VolcanoChart";
import { VOLCANO_POINT_SAMPLE } from "@/lib/eda/volcanoSelection";

const flush = () => new Promise<void>((resolve) => queueMicrotask(resolve));

const props = {
  points: VOLCANO_POINT_SAMPLE,
  thresholds: {
    effectSizeThreshold: 1,
    significanceThreshold: 0.05,
    direction: "upAndDown" as const,
  },
  significanceField: "adjustedPValue" as const,
  effectSizeLabel: "log2(Fold Change)",
  height: 280,
  testId: "eda-viz-volcano",
};

describe("VolcanoChart", () => {
  it("hands ECharts three scatter series and one mark-line series", async () => {
    render(<VolcanoChart {...props} />);
    await flush();
    const option = setOption.mock.calls[0]?.[0] as {
      series: { type: string; name: string }[];
    };
    expect(option.series.map((s) => s.type)).toEqual([
      "scatter",
      "scatter",
      "scatter",
      "line",
    ]);
    expect(option.series[3]?.name).toBe("Thresholds");
  });

  it("says how many points it could not plot", () => {
    const { getByTestId } = render(<VolcanoChart {...props} />);
    expect(getByTestId("eda-viz-volcano-dropped")).toHaveTextContent(
      "1 point without a p-value was not plotted",
    );
  });
});
```

- [ ] **Run and read the failure.** Expected:
  `Failed to resolve import "./VolcanoChart"`.

- [ ] **Implement** `apps/web/src/lib/components/charts/VolcanoChart.tsx`:

```tsx
"use client";

import type { EChartsOption } from "echarts";

import { EChart } from "./EChart";
import { readChartTokens } from "./chartTheme";
import { buildVolcanoOption } from "./volcano.options";
import type {
  VolcanoPointInput,
  VolcanoSignificanceField,
  VolcanoThresholds,
} from "./types";

export interface VolcanoChartProps {
  points: readonly VolcanoPointInput[];
  thresholds: VolcanoThresholds;
  significanceField: VolcanoSignificanceField;
  effectSizeLabel: string;
  height: number;
  testId: string;
}

export function VolcanoChart(props: VolcanoChartProps) {
  const tokens = readChartTokens();
  const model = buildVolcanoOption({
    points: props.points,
    thresholds: props.thresholds,
    significanceField: props.significanceField,
    effectSizeLabel: props.effectSizeLabel,
    tokens,
  });

  const option: EChartsOption = {
    animation: false,
    grid: { left: 56, right: 16, top: 24, bottom: 44 },
    xAxis: { type: "value", name: model.xAxis.name, nameLocation: "middle", nameGap: 26 },
    yAxis: { type: "value", name: model.yAxis.name, nameLocation: "middle", nameGap: 40 },
    legend: { top: 0, right: 0, icon: "circle" },
    tooltip: {
      trigger: "item",
      formatter: (p: { value: [number, number, string] }) =>
        `${p.value[2]}<br/>effect ${p.value[0].toFixed(3)}<br/>-log10(p) ${p.value[1].toFixed(2)}`,
    },
    dataZoom: [{ type: "inside", xAxisIndex: 0 }, { type: "inside", yAxisIndex: 0 }],
    series: [
      ...model.series.map((s) => ({
        type: "scatter" as const,
        name: s.name,
        data: s.data,
        symbolSize: 4,
        large: true,
        largeThreshold: 2000,
        itemStyle: s.itemStyle,
      })),
      {
        type: "line" as const,
        name: "Thresholds",
        data: [],
        silent: true,
        markLine: {
          symbol: "none",
          label: { show: false },
          lineStyle: { color: tokens.border, type: "dashed" },
          data: model.thresholdLines.map((line) =>
            line.axis === "x" ? { xAxis: line.value } : { yAxis: line.value },
          ),
        },
      },
    ],
  };

  return (
    <div className="w-full">
      <EChart
        option={option}
        height={props.height}
        ariaLabel={`Volcano plot, ${model.series[1]?.data.length ?? 0} higher in group B and ${model.series[2]?.data.length ?? 0} higher in group A`}
        testId={props.testId}
      />
      {model.droppedRowCount > 0 && (
        <p
          data-testid={`${props.testId}-dropped`}
          className="mt-1 text-[11px] text-muted-foreground"
        >
          {model.droppedRowCount === 1
            ? "1 point without a p-value was not plotted"
            : `${model.droppedRowCount} points without a p-value were not plotted`}
        </p>
      )}
    </div>
  );
}
```

`large: true` with `largeThreshold: 2000` is what keeps thousands of points
interactive on canvas.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/lib/components/charts/VolcanoChart.test.tsx`.

### Task A7: one category builder, two chart components

Both EDA shapes are parallel arrays: the distribution series carries
`labels: string[]` and `values: number[]`, and the upstream barplot carries
`label[]` and `value[]` ([../visualizations.md](../visualizations.md),
[../subsetting-and-tabular.md](../subsetting-and-tabular.md)). The alignment
algorithm is therefore identical for both, and one builder serves both charts.
`HistogramChart` and `BarChart` differ only in their `barMode` vocabulary and in
whether the bars touch, which is the dataviz form rule for continuous against
categorical.

- [ ] **Failing test.** Create
  `apps/web/src/lib/components/charts/category.options.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { CHART_TOKEN_FALLBACKS } from "./chartTheme";
import { buildCategoryOption } from "./category.options";

const distribution = [
  {
    name: "Subset",
    labels: ["[0.0,5.0)", "[5.0,10.0)", "[10.0,15.0)"],
    values: [13, 3254, 31990],
  },
];

const overlaid = [
  { name: "febrile", labels: ["wildtype", "mutant"], values: [2, 2] },
  { name: "normal", labels: ["mutant", "double mutant"], values: [5, 1] },
];

describe("buildCategoryOption", () => {
  it("keeps a single series label order as the categories", () => {
    const option = buildCategoryOption({
      series: distribution,
      stacked: true,
      valueLabel: "Records",
      tokens: CHART_TOKEN_FALLBACKS,
    });
    expect(option.categories).toEqual([
      "[0.0,5.0)",
      "[5.0,10.0)",
      "[10.0,15.0)",
    ]);
    expect(option.series[0]?.values).toEqual([13, 3254, 31990]);
  });

  it("unions labels across series in first-seen order", () => {
    const option = buildCategoryOption({
      series: overlaid,
      stacked: true,
      valueLabel: "Samples",
      tokens: CHART_TOKEN_FALLBACKS,
    });
    expect(option.categories).toEqual(["wildtype", "mutant", "double mutant"]);
  });

  it("aligns each series to the unioned categories with zero for a missing label", () => {
    const option = buildCategoryOption({
      series: overlaid,
      stacked: true,
      valueLabel: "Samples",
      tokens: CHART_TOKEN_FALLBACKS,
    });
    expect(option.series[0]?.values).toEqual([2, 2, 0]);
    expect(option.series[1]?.values).toEqual([0, 5, 1]);
  });

  it("stops at the shorter of labels and values rather than emitting undefined", () => {
    const option = buildCategoryOption({
      series: [{ name: "Short", labels: ["a", "b"], values: [1] }],
      stacked: false,
      valueLabel: "Records",
      tokens: CHART_TOKEN_FALLBACKS,
    });
    expect(option.categories).toEqual(["a"]);
    expect(option.series[0]?.values).toEqual([1]);
  });

  it("sets one stack id when stacked and none when not", () => {
    expect(
      buildCategoryOption({
        series: overlaid,
        stacked: true,
        valueLabel: "Samples",
        tokens: CHART_TOKEN_FALLBACKS,
      }).series.map((s) => s.stack),
    ).toEqual(["total", "total"]);
    expect(
      buildCategoryOption({
        series: overlaid,
        stacked: false,
        valueLabel: "Samples",
        tokens: CHART_TOKEN_FALLBACKS,
      }).series.map((s) => s.stack),
    ).toEqual([null, null]);
  });

  it("colors series by token order and wraps past the sixth", () => {
    const option = buildCategoryOption({
      series: overlaid,
      stacked: false,
      valueLabel: "Samples",
      tokens: CHART_TOKEN_FALLBACKS,
    });
    expect(option.series.map((s) => s.color)).toEqual([
      CHART_TOKEN_FALLBACKS.series[0],
      CHART_TOKEN_FALLBACKS.series[1],
    ]);
  });
});
```

- [ ] **Run and read the failure.** Expected:
  `Failed to resolve import "./category.options"`.

- [ ] **Implement** `apps/web/src/lib/components/charts/category.options.ts`:

```ts
import type { ChartTokens } from "./chartTheme";
import type { EdaCategorySeries } from "./types";

export interface CategoryOptionModel {
  categories: string[];
  series: { name: string; values: number[]; color: string; stack: string | null }[];
  valueLabel: string;
}

export interface BuildCategoryOptionArgs {
  series: readonly EdaCategorySeries[];
  stacked: boolean;
  valueLabel: string;
  tokens: ChartTokens;
}

/** Pair a series' labels with its values, stopping at the shorter array. */
function pairs(series: EdaCategorySeries): [string, number][] {
  const length = Math.min(series.labels.length, series.values.length);
  const out: [string, number][] = [];
  for (let i = 0; i < length; i += 1) {
    const label = series.labels[i];
    const value = series.values[i];
    if (label === undefined || value === undefined) continue;
    out.push([label, value]);
  }
  return out;
}

export function buildCategoryOption(
  args: BuildCategoryOptionArgs,
): CategoryOptionModel {
  const paired = args.series.map(pairs);
  const categories: string[] = [];
  for (const series of paired) {
    for (const [label] of series) {
      if (!categories.includes(label)) categories.push(label);
    }
  }
  const fallback = args.tokens.series[0] ?? "hsl(215 70% 50%)";
  return {
    categories,
    valueLabel: args.valueLabel,
    series: args.series.map((series, index) => {
      const byLabel = new Map(paired[index] ?? []);
      return {
        name: series.name,
        values: categories.map((label) => byLabel.get(label) ?? 0),
        color: args.tokens.series[index % args.tokens.series.length] ?? fallback,
        stack: args.stacked ? "total" : null,
      };
    }),
  };
}
```

- [ ] **Implement `HistogramChart.tsx`.** It translates
  `barMode: "overlay" | "stack"` into `stacked`, composes the ECharts option
  with `xAxis: { type: "category", data: model.categories }`,
  `yAxis: { type: "value", name: model.valueLabel }`,
  `tooltip: { trigger: "axis", axisPointer: { type: "shadow" } }`, and one
  `{ type: "bar", name, data: values, itemStyle: { color }, barCategoryGap: "0%", ...(stack !== null ? { stack } : {}) }`
  series per entry. Note the conditional spread: `exactOptionalPropertyTypes`
  refuses `stack: undefined`. `barCategoryGap: "0%"` is the continuous form:
  adjacent bars, no gap.

- [ ] **Implement `BarChart.tsx`.** Identical, except it translates
  `barMode: "group" | "stack"` into `stacked` and uses
  `barCategoryGap: "30%"` so categories read as separate.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/lib/components/charts/category.options.test.ts`.

### Task A8: removed - BoxplotChart left the contract

The session lead removed `BoxplotChart` from the pinned contract at plan
time: the settled part payloads carry no boxplot statistics, no route
returns fences, and nothing in batches 6 or 7 consumes it. Build nothing
here. The chart returns with the first payload that carries
`lowerfence/q1/median/q3/upperfence`, as its own task, with a consumer.

### Task A9: ScatterChart

Its consumer is the viz part's `chart: "scatter"`, which is the same point
cloud as the volcano with no threshold guides: x is the effect size and y is
`-log10(p-value)`. The coordinates are numbers by the time they reach here, and
a caller can still compute a non-finite y, so the builder drops and counts.

- [ ] **Failing test.** Create
  `apps/web/src/lib/components/charts/scatter.options.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { CHART_TOKEN_FALLBACKS } from "./chartTheme";
import { buildScatterOption } from "./scatter.options";

const args = {
  series: [
    {
      name: "Genes",
      x: [3.94437533216012, -2.5, 0.4],
      y: [4.708, 3, Number.POSITIVE_INFINITY],
      pointIds: ["PF3D7_0100200", "PF3D7_0100300", "PF3D7_0100400"],
    },
    { name: "Unlabelled", x: [-12.5], y: [3.5] },
  ],
  xAxis: { variableId: "effectSize", displayName: "log2(Fold Change)" },
  yAxis: { variableId: "pValue", displayName: "-log10(p-value)" },
  tokens: CHART_TOKEN_FALLBACKS,
};

describe("buildScatterOption", () => {
  it("keeps each finite coordinate pair", () => {
    const option = buildScatterOption(args);
    expect(option.series[0]?.points[0]).toEqual([
      3.94437533216012,
      4.708,
      "PF3D7_0100200",
    ]);
  });

  it("labels a point with its own id when pointIds is present", () => {
    const option = buildScatterOption(args);
    expect(option.series[0]?.points[1]?.[2]).toBe("PF3D7_0100300");
  });

  it("falls back to the series name when pointIds is absent", () => {
    const option = buildScatterOption(args);
    expect(option.series[1]?.points[0]?.[2]).toBe("Unlabelled");
  });

  it("drops a point whose coordinate is not finite and counts it", () => {
    const option = buildScatterOption(args);
    expect(option.series[0]?.points).toHaveLength(2);
    expect(option.droppedPointCount).toBe(1);
  });

  it("stops at the shorter of x and y", () => {
    const option = buildScatterOption({
      ...args,
      series: [{ name: "Ragged", x: [1, 2, 3], y: [1] }],
    });
    expect(option.series[0]?.points).toHaveLength(1);
  });

  it("names the axes from the labels it is given", () => {
    const option = buildScatterOption(args);
    expect(option.xAxisName).toBe("log2(Fold Change)");
    expect(option.yAxisName).toBe("-log10(p-value)");
  });

  it("colors series by token order", () => {
    const option = buildScatterOption(args);
    expect(option.series.map((s) => s.color)).toEqual([
      CHART_TOKEN_FALLBACKS.series[0],
      CHART_TOKEN_FALLBACKS.series[1],
    ]);
  });
});
```

- [ ] **Run and read the failure.** Expected:
  `Failed to resolve import "./scatter.options"`.

- [ ] **Implement** `scatter.options.ts` returning
  `{ series: { name, points: [number, number, string][], color }[], xAxisName, yAxisName, droppedPointCount }`
  and `ScatterChart.tsx` composing it with a per-item tooltip that prints the
  third tuple member.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/lib/components/charts/scatter.options.test.ts`.

### Section A close-out

- [ ] `cd apps/web && yarn format`
- [ ] `npx tsc --noEmit && npx eslint src/ && node scripts/check-boundaries.mjs && node scripts/check-weak-assertions.mjs && npx vitest run`
- [ ] Report: the resolved `echarts` version; the exact `echarts/*` import
  specifiers used and the single file they appear in; every file over 200 lines
  with its line count against the 300 limit; confirmation that no boxplot
  file exists (the chart left the contract at plan time); zero-debt statement
  or the debt.

## Implementer B: state, transport, and hydration glue

### Files

**Create**

- `apps/web/src/state/eda.ts`
- `apps/web/src/state/eda.test.ts`
- `apps/web/src/lib/api/eda.ts`
- `apps/web/src/lib/api/eda.test.ts`
- `apps/web/src/features/conversation/content/parts/DataEdaAnalysisState.test.tsx`

**Modify**

- `apps/web/src/features/conversation/content/parts/DataEdaAnalysisState.tsx`
- `apps/web/src/features/conversation/content/parts/DataEdaSubsetPreview.tsx`
- `apps/web/src/features/conversation/content/parts/DataEdaViz.tsx`

Batch 4 created those three renderer files, `content/edaDataParts.ts` and their
registration in `content/contentComponents.ts`, all text-only and all
compiling. This section adds **only the store-hydration glue** to the three
renderers. It creates no file under `features/conversation` and touches neither
`edaDataParts.ts` nor `contentComponents.ts` nor `DataPartRenderer.tsx`. Batch 7
grows the three renderers into chart renderers.

### Interfaces

**Consumes** (from batch 4, by these exact names):

```ts
import type {
  EdaAnalysisState,
  EdaSubsetPreviewPart,
  EdaVizPart,
  EdaEntityCount,
  EdaDistributionSeries,
  EdaFilter,
} from "@pathfinder/shared";
import { edaFilterSchema } from "@pathfinder/shared/generated/zod/edaFilterSchema";
```

Their shapes are quoted in full under "The settled contract this batch codes
against" at the top of this document. `EdaAnalysisState.filters` is
`unknown[]`; `edaFilterSchema` is the generated zod schema for one wire filter,
published by batch 4 alongside its `set-filters` request schema.

**Produces:**

```ts
// state/eda.ts
export interface EdaBinding {
  siteId: string;
  datasetId: string;
  analysisId: string;
}
export interface EdaAnalysisSnapshot {
  analysisId: string;
  revision: number | null;
  siteId: string;
  datasetId: string;
  studyId: string;
  studyDisplayName: string;
  displayName: string;
  numFilters: number;
  numComputations: number;
  filters: EdaFilter[];
  unparsedFilterCount: number;
  filterSummaries: string[];
  entityCounts: EdaEntityCount[];
  canExportRows: boolean;
}
export interface EdaJobSnapshot {
  jobId: string;
  taskId: string | null;
  appName: string;
  status: string;
}
export function parseAnalysisFilters(raw: readonly unknown[]): {
  filters: EdaFilter[];
  unparsedCount: number;
};
export function isEdaJobComplete(job: EdaJobSnapshot): boolean;
export function isEdaJobFailed(job: EdaJobSnapshot): boolean;
export function isEdaJobRunning(job: EdaJobSnapshot): boolean;
export function selectEffectiveFilters(state: EdaState): EdaFilter[];
export const useEdaStore: /* zustand store over EdaState */;
export function useHydrateEdaPart(part: EdaHydratablePart): void;
```

```ts
// lib/api/eda.ts
export async function searchEdaStudies(siteId, query): Promise<EdaStudySearchResponse>;
export function edaStudySearchOptions(siteId: string, query: string);
export async function getEdaStudyDetail(siteId, datasetId): Promise<EdaStudyDetail>;
export function edaStudyDetailOptions(siteId: string, datasetId: string);
export async function countEdaSubset(body: EdaCountRequest): Promise<EdaCountResponse>;
export async function edaDistribution(
  body: EdaDistributionRequest,
): Promise<EdaDistributionSeries>;
export async function edaViz(body: EdaVizRequest): Promise<EdaVizPart>;
export function conversationEdaOptions(conversationId: string);
export async function patchConversationEda(
  conversationId: string,
  body: EdaAnalysisPatch,
): Promise<EdaAnalysisPatchResponse>;
```

### Task B1: the EDA store

The reconcile rule, settled and unchanged from the plan's first draft:

- **The server part always wins.** A `data-eda.analysis-state` part clears
  `localFilters`, so an optimistic tab edit disappears the moment the server
  echoes the document.
- **Keyed by `analysisId` plus `revision`**, where `revision` is a per-binding
  integer mutation counter. A part naming a lower `revision` of the same
  `analysisId` is ignored, because SSE reconnects replay. An equal revision is
  accepted, because a re-emit carries the same document.
- **A different `analysisId` replaces wholesale**, whatever the revision, and
  clears the subset preview, the viz payloads and the jobs.
- **Last write wins when either side's `revision` is null.**

One more rule the settled viz payload requires: it carries the thresholds the
backend used, so the store **adopts them on the first viz part** and stops
adopting them once the researcher has edited the thresholds. Without this the
chart would draw the researcher's defaults against the backend's `retained`
flag and the two would contradict each other on screen.

- [ ] **Failing test.** Create `apps/web/src/state/eda.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";

import { parseAnalysisFilters, useEdaStore } from "./eda";

const FEBRILE = {
  entityId: "ENT_8151325d",
  variableId: "VAR_081ab087",
  type: "stringSet",
  stringSet: ["febrile"],
};

const ANALYSIS_STATE = {
  siteId: "plasmodb",
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  analysisId: "a-1",
  revision: 2,
  studyDisplayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
  displayName: "Febrile samples",
  numFilters: 1,
  numComputations: 0,
  filters: [FEBRILE],
  filterSummaries: ["temperature_condition is febrile"],
  entityCounts: [
    {
      entityId: "ENT_8151325d",
      entityDisplayName: "Sample",
      count: 6,
      unfilteredCount: 12,
    },
  ],
  canExportRows: true,
};

const SUBSET_PREVIEW = {
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

const VIZ = {
  datasetId: "DS_e973eadd57",
  analysisId: "a-1",
  chart: "volcano" as const,
  effectSizeLabel: "log2(Fold Change)",
  effectSizeThreshold: 2,
  significanceThreshold: 0.01,
  effectDirection: "upOnly" as const,
  totalPoints: 5511,
  retainedPoints: 1543,
  points: [
    {
      pointId: "PF3D7_0100200",
      effectSize: 3.94437533216012,
      pValue: 1.95781599815607e-5,
      adjustedPValue: 0.000137772236907279,
      retained: true,
    },
  ],
};

beforeEach(() => {
  useEdaStore.getState().reset();
});

describe("parseAnalysisFilters", () => {
  it("parses a wire filter the generated schema recognises", () => {
    const parsed = parseAnalysisFilters([FEBRILE]);
    expect(parsed.filters).toHaveLength(1);
    expect(parsed.unparsedCount).toBe(0);
  });

  it("drops an entry the schema rejects and counts it", () => {
    const parsed = parseAnalysisFilters([FEBRILE, { type: "notAFilter" }, 7]);
    expect(parsed.filters).toHaveLength(1);
    expect(parsed.unparsedCount).toBe(2);
  });

  it("returns an empty result for an empty array", () => {
    expect(parseAnalysisFilters([])).toEqual({ filters: [], unparsedCount: 0 });
  });
});

describe("useEdaStore.applyAnalysisState", () => {
  it("binds the conversation to the analysis the part names", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    expect(useEdaStore.getState().binding).toEqual({
      siteId: "plasmodb",
      datasetId: "DS_e973eadd57",
      analysisId: "a-1",
    });
  });

  it("keeps the study title and the analysis name apart", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    const analysis = useEdaStore.getState().analysis;
    expect(analysis?.studyDisplayName).toBe(
      "Heat shock response in sensitive mutants (LRR5, DHC)",
    );
    expect(analysis?.displayName).toBe("Febrile samples");
  });

  it("stores the parsed filters, the summaries and the counts", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    const analysis = useEdaStore.getState().analysis;
    expect(analysis?.filters).toHaveLength(1);
    expect(analysis?.unparsedFilterCount).toBe(0);
    expect(analysis?.filterSummaries).toEqual([
      "temperature_condition is febrile",
    ]);
    expect(analysis?.entityCounts[0]?.unfilteredCount).toBe(12);
    expect(analysis?.canExportRows).toBe(true);
  });

  it("counts a filter the generated schema cannot parse instead of hiding it", () => {
    useEdaStore
      .getState()
      .applyAnalysisState({ ...ANALYSIS_STATE, filters: [FEBRILE, { junk: 1 }] });
    const analysis = useEdaStore.getState().analysis;
    expect(analysis?.filters).toHaveLength(1);
    expect(analysis?.unparsedFilterCount).toBe(1);
  });

  it("clears an optimistic local edit, because the server part is the truth", () => {
    useEdaStore.getState().setLocalFilters([]);
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    expect(useEdaStore.getState().localFilters).toBe(null);
  });

  it("ignores a part whose revision is older than the state it holds", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore
      .getState()
      .applyAnalysisState({ ...ANALYSIS_STATE, revision: 1, displayName: "Stale" });
    expect(useEdaStore.getState().analysis?.displayName).toBe("Febrile samples");
  });

  it("accepts an equal revision, because a re-emit carries the same document", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore
      .getState()
      .applyAnalysisState({ ...ANALYSIS_STATE, displayName: "Renamed" });
    expect(useEdaStore.getState().analysis?.displayName).toBe("Renamed");
  });

  it("replaces wholesale when the analysis id changes, whatever the revision", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore
      .getState()
      .applyAnalysisState({ ...ANALYSIS_STATE, analysisId: "a-2", revision: 0 });
    expect(useEdaStore.getState().analysis?.analysisId).toBe("a-2");
    expect(useEdaStore.getState().binding?.analysisId).toBe("a-2");
  });

  it("takes the last write when neither side carries a revision", () => {
    useEdaStore.getState().applyAnalysisState({ ...ANALYSIS_STATE, revision: null });
    useEdaStore
      .getState()
      .applyAnalysisState({ ...ANALYSIS_STATE, revision: null, displayName: "Later" });
    expect(useEdaStore.getState().analysis?.displayName).toBe("Later");
  });

  it("drops the previous analysis preview, plots and jobs on a new analysis", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore.getState().applySubsetPreview(SUBSET_PREVIEW);
    useEdaStore.getState().applyViz(VIZ);
    useEdaStore.getState().applyJob({
      jobId: "db04204e5386396e1ca2cb78469ab6fb",
      taskId: null,
      appName: "differentialexpression",
      status: "complete",
    });
    useEdaStore.getState().applyAnalysisState({ ...ANALYSIS_STATE, analysisId: "a-2" });
    const state = useEdaStore.getState();
    expect(state.subsetPreview).toBe(null);
    expect(state.viz).toEqual({});
    expect(state.jobs).toEqual({});
  });
});

describe("useEdaStore.applySubsetPreview", () => {
  it("keeps the latest preview with its counts and distribution", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore.getState().applySubsetPreview(SUBSET_PREVIEW);
    const preview = useEdaStore.getState().subsetPreview;
    expect(preview?.entityCounts[0]?.count).toBe(6);
    expect(preview?.distribution?.values).toEqual([6, 6]);
  });

  it("ignores a preview for another analysis", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore
      .getState()
      .applySubsetPreview({ ...SUBSET_PREVIEW, analysisId: "other" });
    expect(useEdaStore.getState().subsetPreview).toBe(null);
  });
});

describe("useEdaStore.applyViz", () => {
  it("keys viz payloads by their chart", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore.getState().applyViz(VIZ);
    expect(useEdaStore.getState().viz["volcano"]?.retainedPoints).toBe(1543);
  });

  it("replaces the payload for the same chart", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore.getState().applyViz(VIZ);
    useEdaStore.getState().applyViz({ ...VIZ, retainedPoints: 1200 });
    expect(useEdaStore.getState().viz["volcano"]?.retainedPoints).toBe(1200);
  });

  it("ignores a plot for another analysis", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore.getState().applyViz({ ...VIZ, analysisId: "other" });
    expect(useEdaStore.getState().viz).toEqual({});
  });

  it("adopts the thresholds the backend used, so the chart agrees with retained", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore.getState().applyViz(VIZ);
    expect(useEdaStore.getState().volcanoThresholds).toEqual({
      effectSizeThreshold: 2,
      significanceThreshold: 0.01,
      direction: "upOnly",
    });
  });

  it("leaves a researcher's own thresholds alone", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore.getState().setVolcanoThresholds({
      effectSizeThreshold: 5,
      significanceThreshold: 0.001,
      direction: "downOnly",
    });
    useEdaStore.getState().applyViz(VIZ);
    expect(useEdaStore.getState().volcanoThresholds.effectSizeThreshold).toBe(5);
  });

  it("does not adopt a partial threshold set", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore.getState().applyViz({ ...VIZ, significanceThreshold: null });
    expect(useEdaStore.getState().volcanoThresholds).toEqual({
      effectSizeThreshold: 1,
      significanceThreshold: 0.05,
      direction: "upAndDown",
    });
  });
});

describe("useEdaStore jobs and thresholds", () => {
  it("tracks a compute job by its id", () => {
    useEdaStore.getState().applyJob({
      jobId: "db04204e5386396e1ca2cb78469ab6fb",
      taskId: null,
      appName: "differentialexpression",
      status: "in-progress",
    });
    expect(
      useEdaStore.getState().jobs["db04204e5386396e1ca2cb78469ab6fb"]?.status,
    ).toBe("in-progress");
  });

  it("defaults the volcano thresholds to the upstream defaults", () => {
    expect(useEdaStore.getState().volcanoThresholds).toEqual({
      effectSizeThreshold: 1,
      significanceThreshold: 0.05,
      direction: "upAndDown",
    });
  });

  it("resets every slice", () => {
    useEdaStore.getState().applyAnalysisState(ANALYSIS_STATE);
    useEdaStore.getState().applyViz(VIZ);
    useEdaStore.getState().reset();
    const state = useEdaStore.getState();
    expect(state.analysis).toBe(null);
    expect(state.binding).toBe(null);
    expect(state.viz).toEqual({});
    expect(state.jobs).toEqual({});
  });
});

describe("job status predicates", () => {
  const job = {
    jobId: "j",
    taskId: null,
    appName: "differentialexpression",
    status: "queued",
  };

  it("calls queued and in-progress running", () => {
    expect(isEdaJobRunning({ ...job, status: "queued" })).toBe(true);
    expect(isEdaJobRunning({ ...job, status: "in-progress" })).toBe(true);
  });

  it("calls complete complete and nothing else", () => {
    expect(isEdaJobComplete({ ...job, status: "complete" })).toBe(true);
    expect(isEdaJobComplete({ ...job, status: "expired" })).toBe(false);
  });

  it("calls failed failed and nothing else", () => {
    expect(isEdaJobFailed({ ...job, status: "failed" })).toBe(true);
    expect(isEdaJobFailed({ ...job, status: "no-such-job" })).toBe(false);
  });

  it("calls no-such-job and expired neither running nor complete", () => {
    expect(isEdaJobRunning({ ...job, status: "no-such-job" })).toBe(false);
    expect(isEdaJobComplete({ ...job, status: "no-such-job" })).toBe(false);
    expect(isEdaJobRunning({ ...job, status: "expired" })).toBe(false);
  });
});
```

Add `isEdaJobComplete`, `isEdaJobFailed` and `isEdaJobRunning` to the test
file's import from `./eda`.

- [ ] **Run and read the failure.** `npx vitest run src/state/eda.test.ts`
  Expected: `Failed to resolve import "./eda"`.

- [ ] **Implement** `apps/web/src/state/eda.ts`. Use `createStore` from
  `./middleware`, exactly as `useWorkbenchStore` does; no immer, no persist -
  the analysis lives upstream and is re-hydrated from the event log, so
  persisting it would resurrect a stale document.

```ts
import { useState } from "react";
import type {
  EdaAnalysisState,
  EdaEntityCount,
  EdaFilter,
  EdaSubsetPreviewPart,
  EdaVizPart,
} from "@pathfinder/shared";
import { edaFilterSchema } from "@pathfinder/shared/generated/zod/edaFilterSchema";

import { createStore } from "./middleware";
import type { VolcanoThresholds } from "@/lib/components/charts/types";

export interface EdaBinding {
  siteId: string;
  datasetId: string;
  analysisId: string;
}

export interface EdaAnalysisSnapshot {
  analysisId: string;
  revision: number | null;
  siteId: string;
  datasetId: string;
  studyId: string;
  studyDisplayName: string;
  displayName: string;
  numFilters: number;
  numComputations: number;
  filters: EdaFilter[];
  unparsedFilterCount: number;
  filterSummaries: string[];
  entityCounts: EdaEntityCount[];
  canExportRows: boolean;
}

export interface EdaJobSnapshot {
  jobId: string;
  taskId: string | null;
  appName: string;
  status: string;
}

export function isEdaJobRunning(job: EdaJobSnapshot): boolean {
  return job.status === "queued" || job.status === "in-progress";
}

export function isEdaJobComplete(job: EdaJobSnapshot): boolean {
  return job.status === "complete";
}

export function isEdaJobFailed(job: EdaJobSnapshot): boolean {
  return job.status === "failed";
}

/** The shared models type an analysis's filters as unknown, so each entry is
 * validated here and an unrecognised one is counted, never hidden. */
export function parseAnalysisFilters(raw: readonly unknown[]): {
  filters: EdaFilter[];
  unparsedCount: number;
} {
  const filters: EdaFilter[] = [];
  let unparsedCount = 0;
  for (const entry of raw) {
    const parsed = edaFilterSchema.safeParse(entry);
    if (parsed.success) filters.push(parsed.data);
    else unparsedCount += 1;
  }
  return { filters, unparsedCount };
}

const DEFAULT_THRESHOLDS: VolcanoThresholds = {
  effectSizeThreshold: 1,
  significanceThreshold: 0.05,
  direction: "upAndDround",
};

interface EdaSlice {
  binding: EdaBinding | null;
  analysis: EdaAnalysisSnapshot | null;
  subsetPreview: EdaSubsetPreviewPart | null;
  viz: Record<string, EdaVizPart>;
  jobs: Record<string, EdaJobSnapshot>;
  localFilters: EdaFilter[] | null;
  volcanoThresholds: VolcanoThresholds;
  volcanoThresholdsEdited: boolean;
}

export interface EdaState extends EdaSlice {
  applyAnalysisState: (payload: EdaAnalysisState) => void;
  applySubsetPreview: (payload: EdaSubsetPreviewPart) => void;
  applyViz: (payload: EdaVizPart) => void;
  applyJob: (job: EdaJobSnapshot) => void;
  setLocalFilters: (filters: EdaFilter[] | null) => void;
  setVolcanoThresholds: (thresholds: VolcanoThresholds) => void;
  reset: () => void;
}

const INITIAL: EdaSlice = {
  binding: null,
  analysis: null,
  subsetPreview: null,
  viz: {},
  jobs: {},
  localFilters: null,
  volcanoThresholds: DEFAULT_THRESHOLDS,
  volcanoThresholdsEdited: false,
};

/** A part supersedes the state it holds unless it names an older revision of
 * the same analysis. */
function supersedes(
  current: EdaAnalysisSnapshot | null,
  payload: EdaAnalysisState,
): boolean {
  if (current === null) return true;
  if (current.analysisId !== payload.analysisId) return true;
  if (current.revision === null || payload.revision === null) return true;
  return payload.revision >= current.revision;
}

function snapshotOf(payload: EdaAnalysisState): EdaAnalysisSnapshot {
  const { filters, unparsedCount } = parseAnalysisFilters(payload.filters);
  return {
    analysisId: payload.analysisId,
    revision: payload.revision,
    siteId: payload.siteId,
    datasetId: payload.datasetId,
    studyId: payload.studyId,
    studyDisplayName: payload.studyDisplayName,
    displayName: payload.displayName,
    numFilters: payload.numFilters,
    numComputations: payload.numComputations,
    filters,
    unparsedFilterCount: unparsedCount,
    filterSummaries: payload.filterSummaries,
    entityCounts: payload.entityCounts,
    canExportRows: payload.canExportRows,
  };
}

export const useEdaStore = createStore<EdaState>("EdaStore", (set) => ({
  ...INITIAL,

  applyAnalysisState: (payload) =>
    set((s) => {
      if (!supersedes(s.analysis, payload)) return s;
      const switched = s.analysis?.analysisId !== payload.analysisId;
      return {
        binding: {
          siteId: payload.siteId,
          datasetId: payload.datasetId,
          analysisId: payload.analysisId,
        },
        analysis: snapshotOf(payload),
        localFilters: null,
        ...(switched
          ? {
              subsetPreview: null,
              viz: {},
              jobs: {},
              volcanoThresholds: DEFAULT_THRESHOLDS,
              volcanoThresholdsEdited: false,
            }
          : {}),
      };
    }),

  applySubsetPreview: (payload) =>
    set((s) =>
      s.analysis?.analysisId === payload.analysisId ? { subsetPreview: payload } : s,
    ),

  applyViz: (payload) =>
    set((s) => {
      if (s.analysis?.analysisId !== payload.analysisId) return s;
      const adopt =
        !s.volcanoThresholdsEdited &&
        payload.effectSizeThreshold !== null &&
        payload.significanceThreshold !== null &&
        payload.effectDirection !== null;
      return {
        viz: { ...s.viz, [payload.chart]: payload },
        ...(adopt
          ? {
              volcanoThresholds: {
                effectSizeThreshold: payload.effectSizeThreshold,
                significanceThreshold: payload.significanceThreshold,
                direction: payload.effectDirection,
              },
            }
          : {}),
      };
    }),

  applyJob: (job) => set((s) => ({ jobs: { ...s.jobs, [job.jobId]: job } })),

  setLocalFilters: (filters) => set({ localFilters: filters }),

  setVolcanoThresholds: (thresholds) =>
    set({ volcanoThresholds: thresholds, volcanoThresholdsEdited: true }),

  reset: () => set({ ...INITIAL }),
}));

/** Filters the tab renders: the optimistic local edit while one is pending,
 * otherwise the server document. */
export function selectEffectiveFilters(state: EdaState): EdaFilter[] {
  return state.localFilters ?? state.analysis?.filters ?? [];
}
```

The `adopt` branch narrows the three nullable fields before reading them, which
is what `exactOptionalPropertyTypes` and the null checks together require. Note
the deliberate typo in the sketch above (`upAndDround`): the implementer fixes
it to `upAndDown`, and the store test's default-thresholds case catches it. Do
not copy a sketch without reading it.

- [ ] **Gates.** Run the ladder with `npx vitest run src/state/eda.test.ts`.

### Task B2: the hydration hook and the glue in the three renderers

- [ ] **Failing test.** Create
  `apps/web/src/features/conversation/content/parts/DataEdaAnalysisState.test.tsx`:

```tsx
/**
 * @vitest-environment jsdom
 */
import { beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { useEdaStore } from "@/state/eda";
import { DataEdaAnalysisState } from "./DataEdaAnalysisState";

const PAYLOAD = {
  siteId: "plasmodb",
  datasetId: "DS_e973eadd57",
  studyId: "STUDY_e973eadd57",
  analysisId: "a-1",
  revision: 3,
  studyDisplayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
  displayName: "Febrile samples",
  numFilters: 1,
  numComputations: 0,
  filters: [
    {
      entityId: "ENT_8151325d",
      variableId: "VAR_081ab087",
      type: "stringSet",
      stringSet: ["febrile"],
    },
  ],
  filterSummaries: ["temperature_condition is febrile"],
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

beforeEach(() => {
  useEdaStore.getState().reset();
});

describe("DataEdaAnalysisState", () => {
  it("names the study and each filtered entity count", () => {
    render(<DataEdaAnalysisState data={PAYLOAD} />);
    const card = screen.getByTestId("data-eda-analysis-state");
    expect(card).toHaveTextContent(
      "Heat shock response in sensitive mutants (LRR5, DHC)",
    );
    expect(card).toHaveTextContent("Sample");
    expect(card).toHaveTextContent("34,320");
  });

  it("hydrates the store so the tab reflects a chat-driven change", async () => {
    render(<DataEdaAnalysisState data={PAYLOAD} />);
    await waitFor(() => {
      expect(useEdaStore.getState().analysis?.analysisId).toBe("a-1");
    });
    const state = useEdaStore.getState();
    expect(state.analysis?.revision).toBe(3);
    expect(state.analysis?.filters).toHaveLength(1);
    expect(state.binding).toEqual({
      siteId: "plasmodb",
      datasetId: "DS_e973eadd57",
      analysisId: "a-1",
    });
  });

  it("hydrates once for one payload, however many times it re-renders", async () => {
    const { rerender } = render(<DataEdaAnalysisState data={PAYLOAD} />);
    await waitFor(() => {
      expect(useEdaStore.getState().analysis?.revision).toBe(3);
    });
    useEdaStore.getState().setLocalFilters([]);
    rerender(<DataEdaAnalysisState data={PAYLOAD} />);
    expect(useEdaStore.getState().localFilters).toEqual([]);
  });
});
```

The third case is the point of the hook's comparison guard: re-rendering with
the same payload object must not re-dispatch and must not wipe a local edit
made in between.

- [ ] **Run and read the failure.**
  `npx vitest run src/features/conversation/content/parts/DataEdaAnalysisState.test.tsx`
  Expected: the hydration case fails with
  `expected undefined to be "a-1"`, because batch 4's renderer prints text and
  calls nothing.

- [ ] **Implement the hook** in `apps/web/src/state/eda.ts`:

```ts
export type EdaHydratablePart =
  | { kind: "analysis-state"; data: EdaAnalysisState }
  | { kind: "subset-preview"; data: EdaSubsetPreviewPart }
  | { kind: "viz"; data: EdaVizPart };

/** Feed one rendered data part into the store so the tab and the thread show
 * the same analysis. */
export function useHydrateEdaPart(part: EdaHydratablePart): void {
  const [appliedData, setAppliedData] = useState<unknown>(null);
  if (appliedData !== part.data) {
    setAppliedData(part.data);
    queueMicrotask(() => {
      const store = useEdaStore.getState();
      if (part.kind === "analysis-state") store.applyAnalysisState(part.data);
      else if (part.kind === "subset-preview") store.applySubsetPreview(part.data);
      else store.applyViz(part.data);
    });
  }
}
```

The comparison is on `part.data`, not on `part`: the wrapper object is fresh
every render and the payload object is not. The hook lives in `state/` because
`lib/` may not import `state/` and `features/` may.

- [ ] **Add the glue to the three renderers**, one line each, plus whatever the
  test above requires of `DataEdaAnalysisState`'s text. Batch 4's bodies stay;
  batch 7 grows them.

```tsx
// parts/DataEdaAnalysisState.tsx
useHydrateEdaPart({ kind: "analysis-state", data });
// parts/DataEdaSubsetPreview.tsx
useHydrateEdaPart({ kind: "subset-preview", data });
// parts/DataEdaViz.tsx
useHydrateEdaPart({ kind: "viz", data });
```

`DataEdaAnalysisState` prints `studyDisplayName` as its heading and one line per
`entityCounts` entry, `entityDisplayName` with `count.toLocaleString()`. Leave
the other two renderers' text as batch 4 wrote it.

- [ ] **Gates.** Run the ladder with
  `npx vitest run src/features/conversation/content/parts/DataEdaAnalysisState.test.tsx src/features/conversation/content/dataPartDispatch.test.tsx`.
  `dataPartDispatch.test.tsx` already exists and covers the dispatcher; read it
  and add a case for one EDA kind if it enumerates kinds explicitly.

### Task B3: the transport wrappers

The routes are pinned in [overview.md](overview.md). Two settled facts about
them:

1. `GET /api/v1/eda/studies` and `GET /api/v1/eda/studies/{dataset_id}` take a
   `siteId` query parameter, because a dataset id is only unique within a site.
2. `PATCH /api/v1/conversations/{id}/eda` is a **five-member discriminated union
   on `action`**, so binding, unbinding, editing filters, running a compute and
   exporting a step all travel one route. That is why the pinned route list
   needs no compute or export endpoint.

```ts
type EdaAnalysisPatch =
  | { action: "bind"; siteId: string; datasetId: string }
  | { action: "set-filters"; filters: EdaFilter[] }
  | { action: "run-compute"; computation: EdaComputationDescriptor }
  | { action: "export-step"; thresholds: VolcanoThresholdsWire | null }
  | { action: "unbind" };

interface EdaAnalysisPatchResponse {
  analysis: EdaAnalysisState | null;
  job: { jobId: string; taskId: string | null; appName: string; status: string } | null;
  step: ConversationResponse | null;
}
```

`VolcanoThresholdsWire` is batch 4's generated `volcanoThresholds` type and
spells the third field `effectDirection`. It is NOT this batch's chart-prop
`VolcanoThresholds`, whose local field is `direction`; the two meet exactly
once, in batch 6's `ExportStepButton`, which maps field by field.

Generated names, as Kubb produced them from batch 4 (import these, never
re-declare the shapes): the PATCH body union is
`PatchConversationEdaMutationRequest` with zod
`patchConversationEdaMutationRequestSchema` (FastAPI inlines the five-way
`action` union at operation scope, so it carries no component name of its
own; the members are `edaBindActionSchema`, `edaSetFiltersActionSchema`,
`edaRunComputeActionSchema`, `edaExportStepActionSchema`,
`edaUnbindActionSchema`); the response is `EdaAnalysisPatchResponse` /
`edaAnalysisPatchResponseSchema` with `analysis` required-and-nullable and
`job`, `step` optional-and-nullable; `/distribution` answers
`EdaDistributionSeries` directly (there is no `EdaDistributionResponse`);
the one wire filter schema `edaFilterSchema` exists because batch 4 declares
`EdaFilter` as a `typing.TypeAliasType` (a bare `Annotated` union alias is
inlined by Pydantic and gets no component). Build the local
`EdaAnalysisPatch` type as an alias of the generated union, not a copy.

Three properties of that route the tab depends on:

- **`taskId` is null for a tab-started compute.** There is no
  `background_tasks` row to poll, so the tab must not reach for
  `taskStatusOptions`.
- **`run-compute` is an idempotent submit-or-poll.** The job id is a hash of the
  request ([../computes-and-jobs.md](../computes-and-jobs.md)), so repeating the
  identical `run-compute` action **is** the status poll. Batch 6 polls that way.
- **The PATCH writes no conversation event.** Chat reflects a tab edit on the
  agent's next `data-eda.analysis-state` part, which the store's reconcile rule
  already handles.

- [ ] **Failing test.** Create `apps/web/src/lib/api/eda.test.ts`:

```ts
/**
 * @vitest-environment jsdom
 */
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import {
  countEdaSubset,
  edaDistribution,
  patchConversationEda,
  searchEdaStudies,
} from "./eda";

const BASE = "http://localhost:3000";
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("searchEdaStudies", () => {
  it("sends the query and the site and returns the study rows", async () => {
    let seenUrl = "";
    server.use(
      http.get(`${BASE}/api/v1/eda/studies`, ({ request }) => {
        seenUrl = request.url;
        return HttpResponse.json({
          studies: [
            {
              datasetId: "DS_e973eadd57",
              studyId: "STUDY_e973eadd57",
              displayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
              shortDisplayName: "Heat shock",
              lastModified: "2026-05-27T20:00:00-04:00",
              sourceType: "curated",
            },
          ],
        });
      }),
    );
    const result = await searchEdaStudies("plasmodb", "heat shock");
    expect(seenUrl).toContain("q=heat+shock");
    expect(seenUrl).toContain("siteId=plasmodb");
    expect(result.studies[0]?.datasetId).toBe("DS_e973eadd57");
  });
});

describe("countEdaSubset", () => {
  it("posts the filters and returns filtered and unfiltered counts", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${BASE}/api/v1/eda/count`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({
          counts: [
            {
              entityId: "ENT_8151325d",
              entityDisplayName: "Sample",
              count: 6,
              unfilteredCount: 12,
            },
          ],
        });
      }),
    );
    const result = await countEdaSubset({
      siteId: "plasmodb",
      datasetId: "DS_e973eadd57",
      entityIds: ["ENT_8151325d"],
      filters: [
        {
          entityId: "ENT_8151325d",
          variableId: "VAR_081ab087",
          type: "stringSet",
          stringSet: ["febrile"],
        },
      ],
    });
    expect(body).toEqual({
      siteId: "plasmodb",
      datasetId: "DS_e973eadd57",
      entityIds: ["ENT_8151325d"],
      filters: [
        {
          entityId: "ENT_8151325d",
          variableId: "VAR_081ab087",
          type: "stringSet",
          stringSet: ["febrile"],
        },
      ],
    });
    expect(result.counts[0]?.count).toBe(6);
    expect(result.counts[0]?.unfilteredCount).toBe(12);
  });
});

describe("edaDistribution", () => {
  it("returns the settled distribution series with its statistics", async () => {
    server.use(
      http.post(`${BASE}/api/v1/eda/distribution`, () =>
        HttpResponse.json({
          variableId: "EUPATH_0000047",
          variableDisplayName: "Hemoglobin",
          labels: ["[0.0,5.0)", "[5.0,10.0)", "[10.0,15.0)"],
          values: [13, 3254, 31990],
          subsetSize: 48721,
          numVarValues: 36570,
          numMissingCases: 12151,
          isMultiValued: false,
        }),
      ),
    );
    const result = await edaDistribution({
      siteId: "plasmodb",
      datasetId: "DS_e973eadd57",
      entityId: "ENT_8151325d",
      variableId: "EUPATH_0000047",
      filters: [],
    });
    expect(result.values).toEqual([13, 3254, 31990]);
    expect(result.numMissingCases).toBe(12151);
  });
});

describe("patchConversationEda", () => {
  it("sends the set-filters action and returns the new analysis state", async () => {
    let body: unknown = null;
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({
          analysis: {
            siteId: "plasmodb",
            datasetId: "DS_e973eadd57",
            studyId: "STUDY_e973eadd57",
            analysisId: "a-1",
            revision: 4,
            studyDisplayName: "Heat shock response",
            displayName: "Febrile samples",
            numFilters: 0,
            numComputations: 0,
            filters: [],
            filterSummaries: [],
            entityCounts: [],
            canExportRows: true,
          },
          job: null,
          step: null,
        });
      }),
    );
    const result = await patchConversationEda("conv-1", {
      action: "set-filters",
      filters: [],
    });
    expect(body).toEqual({ action: "set-filters", filters: [] });
    expect(result.analysis?.revision).toBe(4);
  });

  it("sends unbind with no other field and accepts a null analysis", async () => {
    let body: unknown = null;
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ analysis: null, job: null, step: null });
      }),
    );
    const result = await patchConversationEda("conv-1", { action: "unbind" });
    expect(body).toEqual({ action: "unbind" });
    expect(result.analysis).toBe(null);
  });

  it("returns the job reference a run-compute answers with", async () => {
    server.use(
      http.patch(`${BASE}/api/v1/conversations/conv-1/eda`, () =>
        HttpResponse.json({
          analysis: null,
          job: {
            jobId: "db04204e5386396e1ca2cb78469ab6fb",
            taskId: null,
            appName: "differentialexpression",
            status: "in-progress",
          },
          step: null,
        }),
      ),
    );
    const result = await patchConversationEda("conv-1", {
      action: "run-compute",
      computation: {
        type: "differentialexpression",
        configuration: {
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
    expect(result.job?.taskId).toBe(null);
    expect(result.job?.status).toBe("in-progress");
  });
});
```

- [ ] **Run and read the failure.** `npx vitest run src/lib/api/eda.test.ts`
  Expected: `Failed to resolve import "./eda"`.

- [ ] **Implement** `apps/web/src/lib/api/eda.ts`, copying the idiom of
  `apps/web/src/lib/api/tasks.ts` exactly: every call goes through
  `requestJson(schema, path, args)` from `./http`, and every reusable read is
  also exposed as a `queryOptions(...)` factory. The zod schemas come from batch
  4's generated output.

```ts
"use client";

import { queryOptions } from "@tanstack/react-query";
import type {
  EdaAnalysisPatch,
  EdaAnalysisPatchResponse,
  EdaCountRequest,
  EdaCountResponse,
  EdaDistributionRequest,
  EdaDistributionSeries,
  EdaStudyDetail,
  EdaStudySearchResponse,
  EdaVizPart,
  EdaVizRequest,
  ConversationEdaBindingResponse,
} from "@pathfinder/shared";
import { conversationEdaBindingResponseSchema } from "@pathfinder/shared/generated/zod/conversationEdaBindingResponseSchema";
import { edaAnalysisPatchResponseSchema } from "@pathfinder/shared/generated/zod/edaAnalysisPatchResponseSchema";
import { edaCountResponseSchema } from "@pathfinder/shared/generated/zod/edaCountResponseSchema";
import { edaDistributionSeriesSchema } from "@pathfinder/shared/generated/zod/edaDistributionSeriesSchema";
import { edaStudyDetailSchema } from "@pathfinder/shared/generated/zod/edaStudyDetailSchema";
import { edaStudySearchResponseSchema } from "@pathfinder/shared/generated/zod/edaStudySearchResponseSchema";
import { edaVizPartSchema } from "@pathfinder/shared/generated/zod/edaVizPartSchema";

import { requestJson } from "./http";

export async function searchEdaStudies(
  siteId: string,
  query: string,
): Promise<EdaStudySearchResponse> {
  return await requestJson(edaStudySearchResponseSchema, "/api/v1/eda/studies", {
    query: { siteId, q: query },
  });
}

export function edaStudySearchOptions(siteId: string, query: string) {
  return queryOptions({
    queryKey: ["eda", "studies", siteId, query] as const,
    queryFn: () => searchEdaStudies(siteId, query),
    enabled: query.trim().length >= 2,
    staleTime: 60_000,
  });
}

export async function getEdaStudyDetail(
  siteId: string,
  datasetId: string,
): Promise<EdaStudyDetail> {
  return await requestJson(edaStudyDetailSchema, `/api/v1/eda/studies/${datasetId}`, {
    query: { siteId },
  });
}

export function edaStudyDetailOptions(siteId: string, datasetId: string) {
  return queryOptions({
    queryKey: ["eda", "study", siteId, datasetId] as const,
    queryFn: () => getEdaStudyDetail(siteId, datasetId),
    staleTime: Infinity,
  });
}

export async function countEdaSubset(body: EdaCountRequest): Promise<EdaCountResponse> {
  return await requestJson(edaCountResponseSchema, "/api/v1/eda/count", {
    method: "POST",
    body,
  });
}

export async function edaDistribution(
  body: EdaDistributionRequest,
): Promise<EdaDistributionSeries> {
  return await requestJson(edaDistributionSeriesSchema, "/api/v1/eda/distribution", {
    method: "POST",
    body,
  });
}

export async function edaViz(body: EdaVizRequest): Promise<EdaVizPart> {
  return await requestJson(edaVizPartSchema, "/api/v1/eda/viz", {
    method: "POST",
    body,
  });
}

export function conversationEdaOptions(conversationId: string) {
  return queryOptions({
    queryKey: ["conversations", conversationId, "eda"] as const,
    queryFn: () =>
      requestJson(
        conversationEdaBindingResponseSchema,
        `/api/v1/conversations/${conversationId}/eda`,
      ),
    staleTime: 0,
  });
}

export async function patchConversationEda(
  conversationId: string,
  body: EdaAnalysisPatch,
): Promise<EdaAnalysisPatchResponse> {
  return await requestJson(
    edaAnalysisPatchResponseSchema,
    `/api/v1/conversations/${conversationId}/eda`,
    { method: "PATCH", body },
  );
}
```

`ConversationEdaBindingResponse` is `{ analysis: EdaAnalysisState | null }`.
`/api/v1/eda/distribution` returns the settled `EdaDistributionSeries`, the same
type the subset-preview part embeds, so there is exactly one representation of a
distribution on the frontend. If batch 4's generated schema name differs from
`edaDistributionSeriesSchema`, use the generated name and report the mismatch;
never redeclare the type by hand.

- [ ] **Gates.** Run the ladder with `npx vitest run src/lib/api/eda.test.ts`.

### Section B close-out

- [ ] `cd apps/web && yarn format`
- [ ] `npx tsc --noEmit && npx eslint src/ && node scripts/check-boundaries.mjs && node scripts/check-weak-assertions.mjs && npx vitest run`
- [ ] Report: every generated type or zod schema name that differed from the
  name used in this document, listed one per line; the diff to each of the three
  renderer files, which must be the hydration call plus, for
  `DataEdaAnalysisState`, its text; zero-debt statement or the debt.

## Verifier

Re-run, from a clean checkout of the implementers' branches:

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

Read every file both implementers created or modified. Then hunt these traps by
name:

1. **A `useEffect` anywhere.** Grep the diff for `useEffect`. Also reject
   `useLayoutEffect` imported from `react`. `useIsomorphicLayoutEffect` from
   `usehooks-ts` is permitted only if a task card asked for it; no card here
   does.
2. **`useMemo`, `useCallback` or `memo`.**
3. **A ref callback that does not return its teardown**, or an `echarts`
   instance disposed anywhere other than that teardown.
4. **An unstable ref callback.** `EChart`'s mount callback must be held in
   `useState` and must close over setters only. If it closes over `option`, the
   chart re-initialises every render: reject.
5. **A bare `import ... from "echarts"`**, or an `echarts/*` import in any file
   other than `echartsRegistry.ts`.
6. **`echarts-for-react` in `package.json`.**
7. **A chart or a selector reading `pValue` without handling both `undefined`
   and `null`.** The field is `pValue?: number | null`; one live row of 5511
   carried neither p-value.
8. **`pointID` with a capital ID**, or a `Number.parseFloat` on a viz field.
   The part is already normalized to `pointId` and to numbers; parsing a number
   again is a sign the implementer coded against the upstream wire.
9. **A fabricated p-value floor.** There is no `pValueFloor` on the part and no
   such prop on any chart. A hardcoded `1e-200` anywhere in `lib/` is a FAIL.
10. **The study title in the wrong field.** `studyDisplayName` is the study,
    `displayName` is the analysis. A card or a store field that conflates them
    is a FAIL.
11. **A filter read straight out of `EdaAnalysisState.filters` without
    `edaFilterSchema.safeParse`,** or an unparsed entry silently dropped without
    incrementing `unparsedFilterCount`.
12. **A component calling `fetch`.** Grep for `fetch(` outside `lib/api/`.
13. **A cross-feature import**, or a `lib/` file importing `@/features/` or
    `@/state/`. `lib/eda/volcanoSelection.ts` may import
    `@/lib/components/charts/types` and nothing else.
14. **A new entry in `CROSS_FEATURE_EXCEPTIONS`** in
    `scripts/check-boundaries.mjs`. No task in this batch needs one.
15. **A file created under `features/conversation` by section B**, or an edit to
    `edaDataParts.ts`, `contentComponents.ts` or `DataPartRenderer.tsx`. Batch 4
    owns those.
16. **A test whose assertions are all weak matchers**, or a test asserting
    existence rather than a value. Every option-builder test must pin a number
    or an array.
17. **A file over 300 eslint-counted lines**, and any file where the implementer
    silenced `max-lines`.
18. **A `data-eda.*` string literal spelled differently** from
    `data-eda.analysis-state`, `data-eda.subset-preview`, `data-eda.viz`, or an
    `effectDirection` value outside `upOnly`, `downOnly`, `upAndDown`.
19. **Dead store surface.** Any action, field or exported symbol with no caller
    inside this batch and no named caller in batch 6 or 7. There are no
    exceptions: `BoxplotChart` left the contract, so a boxplot file appearing
    anyway is itself a FAIL.
20. **Smart punctuation** in any new source file or doc, and any em dash in a
    comment.

Report format, mandatory:

```
Batch 5 verification

Gates
  tsc --noEmit              PASS/FAIL  <first error if FAIL>
  eslint src/               PASS/FAIL  <count>
  check-boundaries.mjs      PASS/FAIL  <count>
  check-weak-assertions.mjs PASS/FAIL  <count>
  vitest run                PASS/FAIL  <passed>/<total>, <duration>

Per task
  A1 chartTheme              PASS/FAIL  <evidence: test names run, assertions seen>
  A2 echartsRegistry         PASS/FAIL
  A3 EChart lifecycle        PASS/FAIL
  A4 volcanoSelection        PASS/FAIL
  A5 volcano.options         PASS/FAIL
  A6 VolcanoChart            PASS/FAIL
  A7 category builder + 2    PASS/FAIL
  A8 removed                 confirm no boxplot file exists
  A9 ScatterChart            PASS/FAIL
  B1 useEdaStore             PASS/FAIL
  B2 hydration glue          PASS/FAIL
  B3 lib/api/eda             PASS/FAIL

Generated-name mismatches  (one per line, or NONE)

Traps  (1 to 20, each CLEAN or the file:line that violates it)

Definition of done
  zero debt            YES/NO  <what remains>
  adjacent reconciled  YES/NO  <what was missed>
  tests assert values  YES/NO
```

## Exit criteria

For the session lead to close batch 5:

1. Every gate green, verified by the lead's own run, not a claim.
2. `apps/web/src/lib/components/charts/` holds `EChart.tsx` plus the five pinned
   chart components, each pure props-in, each with a tested pure option builder,
   and every component takes numbers because the parts are already normalized.
3. `useEdaStore` exists in `apps/web/src/state/eda.ts` with the reconcile rule
   under test: server part wins, keyed by `analysisId` plus `revision`, an equal
   revision accepted, last write when either revision is null, and an analysis
   switch clearing the preview, the plots, the jobs and the adopted thresholds.
4. `EdaAnalysisState.filters` is parsed entry by entry with `edaFilterSchema`,
   and an entry the schema rejects is counted in `unparsedFilterCount`, never
   hidden.
5. `apps/web/src/lib/api/eda.ts` wraps all six pinned routes through
   `requestJson` with generated zod schemas, no component calls `fetch`, and the
   PATCH is the settled **five-member** action union
   (`bind`, `set-filters`, `run-compute`, `export-step`, `unbind`) returning
   `{ analysis, job, step }` with `taskId` null for tab-started computes.
6. The three renderer files batch 4 created now hydrate the store, and nothing
   in `edaDataParts.ts`, `contentComponents.ts` or `DataPartRenderer.tsx`
   changed.
7. No boxplot chart file exists: `BoxplotChart` left the contract at plan
   time, and the four remaining pinned charts each have a named consumer.
8. The verifier's report shows all twenty traps CLEAN and "zero debt YES".
