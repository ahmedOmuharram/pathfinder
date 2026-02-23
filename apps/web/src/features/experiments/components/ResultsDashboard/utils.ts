/** Shared formatters for ResultsDashboard sections. */
export function pct(v: number | null | undefined): string {
  if (v == null) return "\u2014";
  return `${(v * 100).toFixed(1)}%`;
}

export function fmtNum(v: number | null | undefined, d = 3): string {
  if (v == null) return "\u2014";
  return v.toFixed(d);
}
