/**
 * Chart theme utilities – maps CSS custom properties (--chart-1 … --chart-6)
 * to colour strings that Recharts / SVG props accept directly.
 */

/** Resolve a chart palette colour at runtime from the computed CSS variables. */
export function getChartColor(index: number): string {
  const style = getComputedStyle(document.documentElement);
  const hsl = style.getPropertyValue(`--chart-${(index % 6) + 1}`).trim();
  return `hsl(${hsl})`;
}

/** Static HSL references that work in JSX without touching the DOM. */
export const CHART_COLORS = {
  positive: "hsl(var(--chart-positive))",
  negative: "hsl(var(--chart-negative))",
  primary: "hsl(var(--chart-1))",
  secondary: "hsl(var(--chart-2))",
  warning: "hsl(var(--chart-3))",
  destructive: "hsl(var(--chart-4))",
  purple: "hsl(var(--chart-5))",
  cyan: "hsl(var(--chart-6))",
} as const;
