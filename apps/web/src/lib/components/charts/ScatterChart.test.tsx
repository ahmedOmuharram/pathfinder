/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render } from "@testing-library/react";

const { setOption } = vi.hoisted(() => ({ setOption: vi.fn() }));
vi.mock("./echartsRegistry", () => ({
  initChart: () => ({
    setOption,
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: () => false,
  }),
}));

import { ScatterChart } from "./ScatterChart";
import {
  applyDistinctChartTokens,
  clearDistinctChartTokens,
  DISTINCT_CHART_TOKENS,
} from "./__fixtures__/chartTokens";

const flush = () => new Promise<void>((resolve) => queueMicrotask(resolve));

const props = {
  series: [
    {
      name: "Genes",
      x: [3.94437533216012, -2.5, 0.4],
      y: [4.708, 3, Number.POSITIVE_INFINITY],
      pointIds: ["PF3D7_0100200", "PF3D7_0100300", "PF3D7_0100400"],
    },
  ],
  xAxis: { variableId: "effectSize", displayName: "log2(Fold Change)" },
  yAxis: { variableId: "pValue", displayName: "-log10(p-value)" },
  height: 280,
  testId: "eda-viz-scatter",
};

type ScatterOption = {
  xAxis: { name: string };
  yAxis: { name: string };
  tooltip: { formatter: (params: unknown) => string };
  series: {
    type: string;
    name: string;
    data: [number, number, string][];
    itemStyle: { color: string };
  }[];
};

beforeEach(applyDistinctChartTokens);
afterEach(clearDistinctChartTokens);

describe("ScatterChart", () => {
  it("hands ECharts one scatter series of plottable points", async () => {
    setOption.mockClear();
    render(<ScatterChart {...props} />);
    await flush();
    const option = setOption.mock.calls[0]?.[0] as ScatterOption;
    expect(option.series.map((s) => s.type)).toEqual(["scatter"]);
    expect(option.series[0]?.data).toEqual([
      [3.94437533216012, 4.708, "PF3D7_0100200"],
      [-2.5, 3, "PF3D7_0100300"],
    ]);
    expect(option.series[0]?.itemStyle.color).toBe(DISTINCT_CHART_TOKENS.series[0]);
  });

  it("names both axes from the labels it is given", async () => {
    setOption.mockClear();
    render(<ScatterChart {...props} />);
    await flush();
    const option = setOption.mock.calls[0]?.[0] as ScatterOption;
    expect(option.xAxis.name).toBe("log2(Fold Change)");
    expect(option.yAxis.name).toBe("-log10(p-value)");
  });

  it("names the point and both coordinates in the tooltip", async () => {
    setOption.mockClear();
    render(<ScatterChart {...props} />);
    await flush();
    const option = setOption.mock.calls[0]?.[0] as ScatterOption;
    expect(option.tooltip.formatter({ value: [-2.5, 3, "PF3D7_0100300"] })).toBe(
      "PF3D7_0100300<br/>log2(Fold Change) -2.5<br/>-log10(p-value) 3",
    );
  });

  it("says how many points it could not plot", () => {
    const { getByTestId } = render(<ScatterChart {...props} />);
    expect(getByTestId("eda-viz-scatter-dropped")).toHaveTextContent(
      "1 point with a missing coordinate was not plotted",
    );
  });
});
