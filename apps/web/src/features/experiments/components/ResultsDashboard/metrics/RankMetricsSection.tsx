import { useMemo } from "react";
import type { RankMetrics } from "@pathfinder/shared";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  ReferenceLine,
} from "recharts";
import { Section } from "../shared/Section";
import { pct, fmtNum } from "../utils";

interface RankMetricsSectionProps {
  rankMetrics: RankMetrics;
}

const K_DISPLAY_ORDER = [10, 25, 50, 100];

export function RankMetricsSection({ rankMetrics }: RankMetricsSectionProps) {
  const kRows = useMemo(() => {
    return K_DISPLAY_ORDER.map((k) => ({
      k,
      precision: rankMetrics.precisionAtK[String(k)] ?? null,
      recall: rankMetrics.recallAtK[String(k)] ?? null,
      enrichment: rankMetrics.enrichmentAtK[String(k)] ?? null,
    })).filter((r) => r.precision !== null);
  }, [rankMetrics]);

  const prCurveData = useMemo(
    () =>
      (rankMetrics.prCurve ?? []).map(([precision, recall]) => ({
        precision,
        recall,
      })),
    [rankMetrics],
  );

  const listSizeData = useMemo(
    () =>
      (rankMetrics.listSizeVsRecall ?? []).map(([size, recall]) => ({
        size,
        recall,
      })),
    [rankMetrics],
  );

  const enrichmentData = useMemo(
    () =>
      kRows.map((r) => ({
        name: `K=${r.k}`,
        enrichment: r.enrichment,
      })),
    [kRows],
  );

  if (kRows.length === 0) return null;

  return (
    <Section title="Rank-Based Metrics">
      <div className="space-y-6">
        {/* P@K / R@K / E@K table */}
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                  K (list size)
                </th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                  Precision@K
                </th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                  Recall@K
                </th>
                <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                  Enrichment@K
                </th>
              </tr>
            </thead>
            <tbody>
              {kRows.map((r) => (
                <tr key={r.k} className="border-b border-border last:border-0">
                  <td className="px-4 py-2 font-mono font-medium">{r.k}</td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">
                    {r.precision != null ? pct(r.precision) : "—"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">
                    {r.recall != null ? pct(r.recall) : "—"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">
                    {r.enrichment != null ? (
                      <span
                        className={
                          r.enrichment > 2
                            ? "text-green-600 dark:text-green-400"
                            : r.enrichment > 1
                              ? "text-blue-600 dark:text-blue-400"
                              : "text-muted-foreground"
                        }
                      >
                        {fmtNum(r.enrichment)}x
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* PR curve */}
          {prCurveData.length > 1 && (
            <div className="rounded-lg border border-border bg-card p-4">
              <h4 className="mb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Precision–Recall Curve
              </h4>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={prCurveData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="recall"
                    label={{
                      value: "Recall",
                      position: "insideBottom",
                      offset: -5,
                      fontSize: 11,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                    domain={[0, 1]}
                  />
                  <YAxis
                    label={{
                      value: "Precision",
                      angle: -90,
                      position: "insideLeft",
                      fontSize: 11,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                    domain={[0, 1]}
                  />
                  <Tooltip
                    formatter={(v) => pct(Number(v ?? 0))}
                    contentStyle={{
                      fontSize: 11,
                      background: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="precision"
                    stroke="hsl(var(--foreground))"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* List size vs recall */}
          {listSizeData.length > 1 && (
            <div className="rounded-lg border border-border bg-card p-4">
              <h4 className="mb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                List Size vs Recall
              </h4>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={listSizeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="size"
                    label={{
                      value: "List Size",
                      position: "insideBottom",
                      offset: -5,
                      fontSize: 11,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  />
                  <YAxis
                    label={{
                      value: "Recall",
                      angle: -90,
                      position: "insideLeft",
                      fontSize: 11,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                    tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                    domain={[0, 1]}
                  />
                  <Tooltip
                    formatter={(v) => pct(Number(v ?? 0))}
                    contentStyle={{
                      fontSize: 11,
                      background: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="recall"
                    stroke="hsl(var(--foreground))"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Enrichment bar chart */}
          {enrichmentData.length > 0 && (
            <div className="rounded-lg border border-border bg-card p-4 lg:col-span-2">
              <h4 className="mb-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Enrichment vs Random
              </h4>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={enrichmentData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                    label={{
                      value: "Fold enrichment",
                      angle: -90,
                      position: "insideLeft",
                      fontSize: 11,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                  />
                  <Tooltip
                    formatter={(v) => `${fmtNum(Number(v ?? 0))}x`}
                    contentStyle={{
                      fontSize: 11,
                      background: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                    }}
                  />
                  <ReferenceLine
                    y={1}
                    stroke="hsl(var(--muted-foreground))"
                    strokeDasharray="4 4"
                    label={{
                      value: "Random",
                      position: "right",
                      fontSize: 10,
                      fill: "hsl(var(--muted-foreground))",
                    }}
                  />
                  <Bar
                    dataKey="enrichment"
                    fill="hsl(var(--primary))"
                    fillOpacity={0.3}
                    stroke="hsl(var(--primary))"
                    strokeWidth={1}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </Section>
  );
}
