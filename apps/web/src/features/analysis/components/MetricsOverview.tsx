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
import { Card } from "@/lib/components/ui/Card";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/lib/components/ui/Tooltip";
import { Separator } from "@/lib/components/ui/Separator";
import { Section } from "./Section";
import { pct, fmtNum } from "../utils/formatters";

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
  if (robustness == null) return null;
  const ci = robustness.rankMetricCis?.[ciKey] ?? robustness.metricCis?.[ciKey];
  if (!ci) return null;
  return (
    <span className="ml-1.5 text-[10px] text-muted-foreground/70 tabular-nums">
      [{fmt(ci.lower)}, {fmt(ci.upper)}]
    </span>
  );
}

function metricValueColor(value: number, raw?: boolean | null): string {
  const normalized = raw === true ? (value + 1) / 2 : value; // MCC is [-1,1]
  if (normalized >= 0.7) return "text-green-600 dark:text-green-400";
  if (normalized >= 0.4) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function MetricsOverview({
  metrics,
  rankMetrics,
  robustness,
}: MetricsOverviewProps) {
  const [showSecondary, setShowSecondary] = useState(false);

  const p50 = rankMetrics?.precisionAtK?.["50"] ?? null;
  const e50 = rankMetrics?.enrichmentAtK?.["50"] ?? null;
  const r50 = rankMetrics?.recallAtK?.["50"] ?? null;

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
      desc: "TP / (TP + FN) \u2014 proportion of true positives correctly identified",
    },
    {
      label: "Specificity",
      value: metrics.specificity,
      desc: "TN / (TN + FP) \u2014 proportion of true negatives correctly identified",
    },
    {
      label: "Precision",
      value: metrics.precision,
      desc: "TP / (TP + FP) \u2014 proportion of predicted positives that are correct",
    },
    {
      label: "F1 Score",
      value: metrics.f1Score,
      desc: "2 \u00d7 (Precision \u00d7 Sensitivity) / (Precision + Sensitivity) \u2014 harmonic mean",
    },
    {
      label: "MCC",
      value: metrics.mcc,
      desc: "Matthews Correlation Coefficient \u2014 balanced measure even with class imbalance, range [-1, 1]",
      raw: true,
    },
    {
      label: "Balanced Accuracy",
      value: metrics.balancedAccuracy,
      desc: "(Sensitivity + Specificity) / 2 \u2014 accounts for class imbalance",
    },
  ];

  const secondary = [
    {
      label: "NPV",
      value: metrics.negativePredictiveValue,
      desc: "TN / (TN + FN) \u2014 negative predictive value",
    },
    {
      label: "FPR",
      value: metrics.falsePositiveRate,
      desc: "FP / (FP + TN) \u2014 false positive rate",
    },
    {
      label: "FNR",
      value: metrics.falseNegativeRate,
      desc: "FN / (FN + TP) \u2014 false negative rate",
    },
    {
      label: "Youden\u2019s J",
      value: metrics.youdensJ,
      raw: true,
      desc: "Sensitivity + Specificity - 1 \u2014 ranges from -1 to 1",
    },
  ];

  return (
    <div data-testid="metrics-overview" className="space-y-6">
      {/* Rank-based summary (promoted above classification metrics) */}
      {(p50 != null || e50 != null) && (
        <Section title="Rank-Based Summary">
          <div className="grid grid-cols-3 gap-4">
            {p50 != null && (
              <Card className="px-5 py-4 text-center">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Precision@50
                </div>
                <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-foreground">
                  {pct(p50)}
                </div>
                <CIBadge ciKey="precision_at_50" robustness={robustness ?? null} />
              </Card>
            )}
            {r50 != null && (
              <Card className="px-5 py-4 text-center">
                <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Recall@50
                </div>
                <div className="mt-1 font-mono text-2xl font-bold tabular-nums text-foreground">
                  {pct(r50)}
                </div>
                <CIBadge ciKey="recall_at_50" robustness={robustness ?? null} />
              </Card>
            )}
            {e50 != null && (
              <Card className="px-5 py-4 text-center">
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
                  robustness={robustness ?? null}
                  fmt={(v) => `${fmtNum(v)}x`}
                />
              </Card>
            )}
          </div>
        </Section>
      )}

      {/* Classification metrics */}
      <Section title="Classification Metrics">
        <Card>
          <div className="grid grid-cols-[1fr_280px] divide-x divide-border max-lg:grid-cols-1 max-lg:divide-x-0 max-lg:divide-y">
            <div>
              {primary.map((m) => (
                <div
                  key={m.label}
                  className="flex items-center justify-between border-b border-border px-5 py-2.5 last:border-b-0"
                >
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="cursor-help">
                        <span className="text-sm font-medium text-foreground">
                          {m.label}
                        </span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="right" className="max-w-xs">
                      <p>{m.desc}</p>
                    </TooltipContent>
                  </Tooltip>
                  <span
                    className={`font-mono text-sm font-semibold tabular-nums ${metricValueColor(m.value, m.raw)}`}
                  >
                    {m.raw === true ? fmtNum(m.value) : pct(m.value)}
                  </span>
                </div>
              ))}

              {showSecondary && (
                <>
                  <Separator />
                  {secondary.map((m) => (
                    <div
                      key={m.label}
                      className="flex items-center justify-between bg-muted/30 px-5 py-2.5"
                    >
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="cursor-help text-sm text-muted-foreground">
                            {m.label}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-xs">
                          <p>{m.desc}</p>
                        </TooltipContent>
                      </Tooltip>
                      <span
                        className={`font-mono text-sm tabular-nums ${metricValueColor(m.value, m.raw)}`}
                      >
                        {m.raw === true ? fmtNum(m.value) : pct(m.value)}
                      </span>
                    </div>
                  ))}
                </>
              )}

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
        </Card>
      </Section>
    </div>
  );
}
