/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

const { setOption } = vi.hoisted(() => ({ setOption: vi.fn() }));
vi.mock("./echartsRegistry", () => ({
  initChart: () => ({
    setOption,
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
  }),
}));

import { HistogramChart } from "./HistogramChart";
import {
  applyDistinctChartTokens,
  clearDistinctChartTokens,
  DISTINCT_CHART_TOKENS,
} from "./__fixtures__/chartTokens";

const flush = () => new Promise<void>((resolve) => queueMicrotask(resolve));

const series = [
  { name: "Subset", labels: ["[0.0,5.0)", "[5.0,10.0)"], values: [13, 3254] },
  { name: "All", labels: ["[0.0,5.0)", "[5.0,10.0)"], values: [40, 4000] },
];

type BarSeries = {
  type: string;
  name: string;
  data: number[];
  barCategoryGap: string;
  barGap?: string;
  stack?: string;
  itemStyle: { color: string; opacity: number };
};

type BarOption = {
  xAxis: { type: string; data: string[] };
  yAxis: { name: string };
  series: BarSeries[];
};

async function optionFor(node: ReactElement): Promise<BarOption> {
  setOption.mockClear();
  render(node);
  await flush();
  return setOption.mock.calls[0]?.[0] as BarOption;
}

beforeEach(applyDistinctChartTokens);
afterEach(clearDistinctChartTokens);

describe("HistogramChart", () => {
  it("names the bin count when the caller gives no label", () => {
    const { getByTestId } = render(
      <HistogramChart
        series={series}
        barMode="overlay"
        valueLabel="Records"
        height={140}
        testId="eda-histogram"
      />,
    );
    expect(getByTestId("eda-histogram")).toHaveAttribute(
      "aria-label",
      "Distribution over 2 bins",
    );
  });

  it("takes the caller's label so a card can name the variable", () => {
    const { getByTestId } = render(
      <HistogramChart
        series={series}
        barMode="overlay"
        valueLabel="Records"
        height={140}
        testId="eda-histogram"
        ariaLabel="Temperature distribution over the subset"
      />,
    );
    expect(getByTestId("eda-histogram")).toHaveAttribute(
      "aria-label",
      "Temperature distribution over the subset",
    );
  });

  it("plots the unioned bins on the category axis and names the value axis", async () => {
    const option = await optionFor(
      <HistogramChart
        series={series}
        barMode="overlay"
        valueLabel="Records"
        height={140}
        testId="eda-histogram"
      />,
    );
    expect(option.xAxis.data).toEqual(["[0.0,5.0)", "[5.0,10.0)"]);
    expect(option.yAxis.name).toBe("Records");
    expect(option.series.map((s) => s.data)).toEqual([
      [13, 3254],
      [40, 4000],
    ]);
  });

  it("draws adjacent bars in the token order of the series", async () => {
    const option = await optionFor(
      <HistogramChart
        series={series}
        barMode="overlay"
        valueLabel="Records"
        height={140}
        testId="eda-histogram"
      />,
    );
    expect(option.series.map((s) => s.type)).toEqual(["bar", "bar"]);
    expect(option.series.map((s) => s.barCategoryGap)).toEqual(["0%", "0%"]);
    expect(option.series.map((s) => s.itemStyle.color)).toEqual([
      DISTINCT_CHART_TOKENS.series[0],
      DISTINCT_CHART_TOKENS.series[1],
    ]);
  });

  it("overlays two distributions in the same slot at reduced opacity", async () => {
    const option = await optionFor(
      <HistogramChart
        series={series}
        barMode="overlay"
        valueLabel="Records"
        height={140}
        testId="eda-histogram"
      />,
    );
    expect(option.series.map((s) => s.barGap)).toEqual(["-100%", "-100%"]);
    expect(option.series[0]?.itemStyle.opacity).toBe(0.7);
    expect("stack" in (option.series[0] ?? {})).toBe(false);
  });

  it("keeps one bar solid and in its own slot when there is a single series", async () => {
    const option = await optionFor(
      <HistogramChart
        series={[series[0] ?? { name: "Subset", labels: [], values: [] }]}
        barMode="overlay"
        valueLabel="Records"
        height={140}
        testId="eda-histogram"
      />,
    );
    expect(option.series[0]?.itemStyle.opacity).toBe(1);
    expect("barGap" in (option.series[0] ?? {})).toBe(false);
  });

  it("stacks both distributions on one stack id when asked", async () => {
    const option = await optionFor(
      <HistogramChart
        series={series}
        barMode="stack"
        valueLabel="Records"
        height={140}
        testId="eda-histogram"
      />,
    );
    expect(option.series.map((s) => s.stack)).toEqual(["total", "total"]);
    expect("barGap" in (option.series[0] ?? {})).toBe(false);
  });
});
