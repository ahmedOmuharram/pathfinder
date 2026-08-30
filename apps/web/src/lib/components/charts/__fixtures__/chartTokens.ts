import type { ChartTokens } from "../chartTheme";

/**
 * Six visibly different series colors. The unresolved set paints one neutral
 * for every series, so an ordering assertion needs a set that can disagree.
 */
const SERIES_TRIPLES = [
  "215 75% 45%",
  "160 65% 33%",
  "28 85% 42%",
  "355 70% 45%",
  "275 55% 50%",
  "192 80% 33%",
];

const INK_TRIPLES = {
  foreground: "215 42% 12%",
  mutedForeground: "215 16% 40%",
  border: "212 20% 89%",
  card: "0 0% 100%",
  background: "210 22% 98%",
};

export const DISTINCT_CHART_TOKENS: ChartTokens = {
  series: SERIES_TRIPLES.map((triple) => `hsl(${triple})`),
  positive: "hsl(160 65% 33%)",
  negative: "hsl(355 70% 45%)",
  foreground: `hsl(${INK_TRIPLES.foreground})`,
  mutedForeground: `hsl(${INK_TRIPLES.mutedForeground})`,
  border: `hsl(${INK_TRIPLES.border})`,
  card: `hsl(${INK_TRIPLES.card})`,
  background: `hsl(${INK_TRIPLES.background})`,
};

const DOCUMENT_TOKENS: Record<string, string> = {
  "--chart-positive": "160 65% 33%",
  "--chart-negative": "355 70% 45%",
  "--foreground": INK_TRIPLES.foreground,
  "--muted-foreground": INK_TRIPLES.mutedForeground,
  "--border": INK_TRIPLES.border,
  "--card": INK_TRIPLES.card,
  "--background": INK_TRIPLES.background,
};

SERIES_TRIPLES.forEach((triple, index) => {
  DOCUMENT_TOKENS[`--chart-${String(index + 1)}`] = triple;
});

/** Writes the fixture onto the document root so `readChartTokens` finds it. */
export function applyDistinctChartTokens(): void {
  for (const [name, value] of Object.entries(DOCUMENT_TOKENS)) {
    document.documentElement.style.setProperty(name, value);
  }
}

export function clearDistinctChartTokens(): void {
  for (const name of Object.keys(DOCUMENT_TOKENS)) {
    document.documentElement.style.removeProperty(name);
  }
}
