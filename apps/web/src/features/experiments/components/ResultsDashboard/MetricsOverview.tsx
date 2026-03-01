import { useState, useMemo } from "react";
import type {
  ExperimentMetrics,
  RankMetrics,
  BootstrapResult,
} from "@pathfinder/shared";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from "recharts";
import { Button } from "@/lib/components/ui/Button";
import { Section } from "./Section";
import { pct, fmtNum } from "./utils";

interface MetricsOverviewProps {
  metrics: ExperimentMetrics;
  rankMetrics?: RankMetrics | null;
  robustness?: BootstrapResult | null;
}

function CIBadge({
  ciKey,
  robustness,
  fmt = pct,
}: {
  ciKey: string;
  robustness?: BootstrapResult | null;
  fmt?: (v: number) => string;
}) {
  if (!robustness) return null;
  const ci = robustness.rankMetricCis[ciKey] ?? robustness.metricCis[ciKey];
  if (!ci) return null;
  return (
    <span className="ml-1.5 text-[10px] text-muted-foreground/70 tabular-nums">
      [{fmt(ci.lower)}, {fmt(ci.upper)}]
    </span>
  );
}

export function MetricsOverview({
  metrics,
  rankMetrics,
  robustness,
}: MetricsOverviewProps) {
  const [showSecondary, setShowSecondary] = useState(false);

  const p50 = rankMetrics?.precisionAtK["50"] ?? null;
  const e50 = rankMetrics?.enrichmentAtK["50"] ?? null;
  const r50 = rankMetrics?.recallAtK["50"] ?? null;

  const radarData = useMemo(
    () => [
      { metric: "Sensitivity", value: metrics.sensitivity },
      { metric: "Specificity", value: metrics.specificity },
      { metric: "Precision", value: metrics.precision },
      { metric: "F1", value: metrics.f1Score },
      { metric: "Bal. Acc.", value: metrics.balancedAccuracy },
      {
        metric: "MCC",
        value: Math.max(0, (metrics.mcc + 1) / 2),
      },
    ],
    [metrics],
  );

  const primary = [
    {
      label: "Sensitivity",
      value: metrics.sensitivity,
      desc: "TP / (TP + FN)",
    },
    {
      label: "Specificity",
      value: metrics.specificity,
      desc: "TN / (TN + FP)",
    },
    {
      label: "Precision",
      value: metrics.precision,
      desc: "TP / (TP + FP)",
    },
    {
      label: "F1 Score",
      value: metrics.f1Score,
      desc: "Harmonic mean of precision & sensitivity",
    },
    {
      label: "MCC",
      value: metrics.mcc,
      desc: "Matthews Correlation Coefficient",
      raw: true,
    },
    {
      label: "Balanced Accuracy",
      value: metrics.balancedAccuracy,
      desc: "(Sensitivity + Specificity) / 2",
    },
  ];

  const secondary = [
    { label: "NPV", value: metrics.negativePredictiveValue },
    { label: "FPR", value: metrics.falsePositiveRate },
    { label: "FNR", value: metrics.falseNegativeRate },
    { label: "Youden\u2019s J", value: metrics.youdensJ, raw: true },
  ];

  return (
    <div data-testid="metrics-overview" className="space-y-6">
      {/* Rank-based summary (promoted above classification metrics) */}
      {(p50 != null || e50 != null) && (
        <Section title="Rank-Based Summary">
          <div className="grid grid-cols-3 gap-4">
            {p50 != null && (
              <div className="rounded-lg border border-border bg-card px-5 py-4 text-center">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Precision@50
                </div>
                <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-foreground">
                  {pct(p50)}
                </div>
                <CIBadge ciKey="precision_at_50" robustness={robustness} />
              </div>
            )}
            {r50 != null && (
              <div className="rounded-lg border border-border bg-card px-5 py-4 text-center">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Recall@50
                </div>
                <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-foreground">
                  {pct(r50)}
                </div>
                <CIBadge ciKey="recall_at_50" robustness={robustness} />
              </div>
            )}
            {e50 != null && (
              <div className="rounded-lg border border-border bg-card px-5 py-4 text-center">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Enrichment@50
                </div>
                <div className="mt-1 font-mono text-2xl font-bold tabular-nums">
                  <span
                    className={
                      e50 > 2
                        ? "text-green-600 dark:text-green-400"
                        : e50 > 1
                          ? "text-blue-600 dark:text-blue-400"
                          : "text-foreground"
                    }
                  >
                    {fmtNum(e50)}x
                  </span>
                </div>
                <CIBadge
                  ciKey="enrichment_at_50"
                  robustness={robustness}
                  fmt={(v) => `${fmtNum(v)}x`}
                />
              </div>
            )}
          </div>
        </Section>
      )}

      {/* Classification metrics */}
      <Section title="Classification Metrics">
        <div className="rounded-lg border border-border bg-card shadow-xs">
          <div className="grid grid-cols-[1fr_280px] divide-x divide-border max-lg:grid-cols-1 max-lg:divide-x-0 max-lg:divide-y">
            <div className="divide-y divide-border">
              {primary.map((m) => (
                <div
                  key={m.label}
                  className="flex items-center justify-between px-5 py-2.5"
                >
                  <div>
                    <span className="text-sm font-medium text-foreground">
                      {m.label}
                    </span>
                    <span className="ml-2 text-xs text-muted-foreground">{m.desc}</span>
                  </div>
                  <span className="font-mono text-sm font-semibold tabular-nums text-foreground">
                    {m.raw ? fmtNum(m.value) : pct(m.value)}
                  </span>
                </div>
              ))}
              {showSecondary &&
                secondary.map((m) => (
                  <div
                    key={m.label}
                    className="flex items-center justify-between bg-muted/30 px-5 py-2.5"
                  >
                    <span className="text-sm text-muted-foreground">{m.label}</span>
                    <span className="font-mono text-sm tabular-nums text-foreground">
                      {m.raw ? fmtNum(m.value) : pct(m.value)}
                    </span>
                  </div>
                ))}
              <div className="px-5 py-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => setShowSecondary(!showSecondary)}
                >
                  {showSecondary ? "Show less" : "Show all metrics"}
                </Button>
              </div>
            </div>

            <div className="flex items-center justify-center p-4 max-lg:py-6">
              <ResponsiveContainer width="100%" height={220}>
                <RadarChart data={radarData} outerRadius="75%">
                  <PolarGrid stroke="hsl(var(--border))" />
                  <PolarAngleAxis
                    dataKey="metric"
                    tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  />
                  <PolarRadiusAxis
                    angle={90}
                    domain={[0, 1]}
                    tick={{ fontSize: 9, fill: "hsl(var(--border))" }}
                    tickCount={5}
                  />
                  <Radar
                    dataKey="value"
                    stroke="hsl(var(--foreground))"
                    fill="hsl(var(--foreground))"
                    fillOpacity={0.12}
                    strokeWidth={1.5}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </Section>
    </div>
  );
}
