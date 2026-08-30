import { hslFromTriple } from "@/lib/color/hsl";

import { UNRESOLVED_SERIES_COLOR } from "./unresolved";

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

/** An unresolved ink role inherits the color of the text around the chart. */
const UNRESOLVED_INK = "currentColor";

/** An unresolved surface role paints nothing. */
const UNRESOLVED_SURFACE = "transparent";

const SERIES_VARS = [
  "--chart-1",
  "--chart-2",
  "--chart-3",
  "--chart-4",
  "--chart-5",
  "--chart-6",
];

export const CHART_TOKEN_FALLBACKS: ChartTokens = {
  series: SERIES_VARS.map(() => UNRESOLVED_SERIES_COLOR),
  positive: UNRESOLVED_SERIES_COLOR,
  negative: UNRESOLVED_SERIES_COLOR,
  foreground: UNRESOLVED_INK,
  mutedForeground: UNRESOLVED_INK,
  border: UNRESOLVED_INK,
  card: UNRESOLVED_SURFACE,
  background: UNRESOLVED_SURFACE,
};

function resolve(
  style: CSSStyleDeclaration | null,
  variable: string,
  fallback: string,
): string {
  if (style === null) return fallback;
  const raw = style.getPropertyValue(variable).trim();
  return raw === "" ? fallback : hslFromTriple(raw);
}

export function readChartTokens(): ChartTokens {
  const style =
    typeof document === "undefined" ? null : getComputedStyle(document.documentElement);
  return {
    series: SERIES_VARS.map((variable) =>
      resolve(style, variable, UNRESOLVED_SERIES_COLOR),
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
