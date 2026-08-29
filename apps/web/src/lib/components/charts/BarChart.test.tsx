/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from "vitest";
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

import { BarChart } from "./BarChart";
import { CHART_TOKEN_FALLBACKS } from "./chartTheme";

const flush = () => new Promise<void>((resolve) => queueMicrotask(resolve));

const series = [
  { name: "febrile", labels: ["wildtype", "mutant"], values: [2, 2] },
  { name: "normal", labels: ["mutant", "double mutant"], values: [5, 1] },
];

type BarSeries = {
  type: string;
  name: string;
  data: number[];
  barCategoryGap: string;
  stack?: string;
  itemStyle: { color: string };
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

describe("BarChart", () => {
  it("aligns both series to the unioned categories", async () => {
    const option = await optionFor(
      <BarChart
        series={series}
        barMode="group"
        valueLabel="Samples"
        height={140}
        testId="eda-bar"
      />,
    );
    expect(option.xAxis.data).toEqual(["wildtype", "mutant", "double mutant"]);
    expect(option.series.map((s) => s.data)).toEqual([
      [2, 2, 0],
      [0, 5, 1],
    ]);
    expect(option.yAxis.name).toBe("Samples");
  });

  it("separates categories with a gap and colors by token order", async () => {
    const option = await optionFor(
      <BarChart
        series={series}
        barMode="group"
        valueLabel="Samples"
        height={140}
        testId="eda-bar"
      />,
    );
    expect(option.series.map((s) => s.barCategoryGap)).toEqual(["30%", "30%"]);
    expect(option.series.map((s) => s.itemStyle.color)).toEqual([
      CHART_TOKEN_FALLBACKS.series[0],
      CHART_TOKEN_FALLBACKS.series[1],
    ]);
  });

  it("leaves grouped bars unstacked", async () => {
    const option = await optionFor(
      <BarChart
        series={series}
        barMode="group"
        valueLabel="Samples"
        height={140}
        testId="eda-bar"
      />,
    );
    expect("stack" in (option.series[0] ?? {})).toBe(false);
  });

  it("puts both series on one stack id when asked", async () => {
    const option = await optionFor(
      <BarChart
        series={series}
        barMode="stack"
        valueLabel="Samples"
        height={140}
        testId="eda-bar"
      />,
    );
    expect(option.series.map((s) => s.stack)).toEqual(["total", "total"]);
  });
});
