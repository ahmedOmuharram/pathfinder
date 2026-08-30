import type { ChartTokens } from "./chartTheme";
import type { EdaCategorySeries } from "./types";
import { UNRESOLVED_SERIES_COLOR } from "./unresolved";

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
  const fallback = args.tokens.series[0] ?? UNRESOLVED_SERIES_COLOR;
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
