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
    expect(option.categories).toEqual(["[0.0,5.0)", "[5.0,10.0)", "[10.0,15.0)"]);
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

  it("gives a seventh series the first token again", () => {
    const seven = Array.from({ length: 7 }, (_, index) => ({
      name: `series-${String(index)}`,
      labels: ["a"],
      values: [index],
    }));
    const option = buildCategoryOption({
      series: seven,
      stacked: false,
      valueLabel: "Records",
      tokens: CHART_TOKEN_FALLBACKS,
    });
    expect(option.series[6]?.color).toBe(CHART_TOKEN_FALLBACKS.series[0]);
    expect(option.series[5]?.color).toBe(CHART_TOKEN_FALLBACKS.series[5]);
  });
});
