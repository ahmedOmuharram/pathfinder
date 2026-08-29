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
