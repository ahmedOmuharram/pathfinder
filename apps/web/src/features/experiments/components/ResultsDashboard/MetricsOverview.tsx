import { useState, useMemo } from "react";
import type { ExperimentMetrics } from "@pathfinder/shared";
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
}

export function MetricsOverview({ metrics }: MetricsOverviewProps) {
  const [showSecondary, setShowSecondary] = useState(false);

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
                  <span className="text-sm font-medium text-foreground">{m.label}</span>
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
  );
}
