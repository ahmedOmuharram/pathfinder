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
    expect(theme.valueAxis.splitLine.lineStyle.color).toBe(
      CHART_TOKEN_FALLBACKS.border,
    );
  });

  it("gives the tooltip the card background and a border", () => {
    const theme = buildChartTheme(CHART_TOKEN_FALLBACKS);
    expect(theme.tooltip.backgroundColor).toBe(CHART_TOKEN_FALLBACKS.card);
    expect(theme.tooltip.borderColor).toBe(CHART_TOKEN_FALLBACKS.border);
  });
});
