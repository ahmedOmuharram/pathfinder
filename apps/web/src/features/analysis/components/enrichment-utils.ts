import type { EnrichmentTerm } from "@pathfinder/shared";

export type SortKey = "termName" | "geneCount" | "foldEnrichment" | "pValue" | "fdr";

export const MAX_CHART_TERMS = 15;
export const DOT_MIN_R = 4;
export const DOT_MAX_R = 14;

/** Map -log10(pValue) onto a blue-to-red gradient for significance. */
export function pvalColor(pValue: number | null): string {
  if (pValue === null) return "hsl(0, 0%, 60%)";
  const negLog = -Math.log10(Math.max(pValue, 1e-20));
  const t = Math.min(negLog / 10, 1);
  const h = 220 - t * 220;
  return `hsl(${h}, ${70 + t * 10}%, ${55 - t * 5}%)`;
}

/** Render a ratio. A null ratio is unbounded, so it has no number. */
export function formatRatio(value: number | null, digits: number): string {
  return value === null ? "Inf" : value.toFixed(digits);
}

/** Render a probability. A null probability is not computable. */
export function formatProbability(value: number | null): string {
  return value === null ? "n/a" : value.toExponential(2);
}

/**
 * Order values ascending. A null ratio is unbounded and a null probability is
 * not computable, so both sort last; reversing the order puts them first.
 */
export function compareNullableAsc(a: number | null, b: number | null): number {
  if (a === null) return b === null ? 0 : 1;
  if (b === null) return -1;
  return a - b;
}

export function fmtCount(n: number): string {
  return n.toLocaleString();
}

/** Truncate a label for chart display. */
export function truncateLabel(label: string, max = 35): string {
  return label.length > max ? label.slice(0, max - 3) + "..." : label;
}

/** Filter terms by p-value threshold. A term with no p-value is not significant. */
export function filterByPThreshold(
  terms: EnrichmentTerm[],
  threshold: number,
): EnrichmentTerm[] {
  return terms.filter((t) => t.pValue !== null && t.pValue <= threshold);
}
