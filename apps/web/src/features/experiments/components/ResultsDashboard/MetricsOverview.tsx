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
      <div className="rounded-lg border border-slate-200 bg-white">
        <div className="grid grid-cols-[1fr_280px] divide-x divide-slate-200 max-lg:grid-cols-1 max-lg:divide-x-0 max-lg:divide-y">
          <div className="divide-y divide-slate-100">
            {primary.map((m) => (
              <div
                key={m.label}
                className="flex items-center justify-between px-5 py-2.5"
              >
                <div>
                  <span className="text-[13px] font-medium text-slate-800">
                    {m.label}
                  </span>
                  <span className="ml-2 text-[11px] text-slate-400">{m.desc}</span>
                </div>
                <span className="font-mono text-[13px] font-semibold tabular-nums text-slate-900">
                  {m.raw ? fmtNum(m.value) : pct(m.value)}
                </span>
              </div>
            ))}
            {showSecondary &&
              secondary.map((m) => (
                <div
                  key={m.label}
                  className="flex items-center justify-between bg-slate-50/50 px-5 py-2.5"
                >
                  <span className="text-[13px] text-slate-600">{m.label}</span>
                  <span className="font-mono text-[13px] tabular-nums text-slate-700">
                    {m.raw ? fmtNum(m.value) : pct(m.value)}
                  </span>
                </div>
              ))}
            <div className="px-5 py-2">
              <button
                type="button"
                onClick={() => setShowSecondary(!showSecondary)}
                className="text-xs text-slate-400 transition hover:text-slate-600"
              >
                {showSecondary ? "Show less" : "Show all metrics"}
              </button>
            </div>
          </div>

          <div className="flex items-center justify-center p-4 max-lg:py-6">
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={radarData} outerRadius="75%">
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis
                  dataKey="metric"
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                />
                <PolarRadiusAxis
                  angle={90}
                  domain={[0, 1]}
                  tick={{ fontSize: 9, fill: "#cbd5e1" }}
                  tickCount={5}
                />
                <Radar
                  dataKey="value"
                  stroke="#334155"
                  fill="#334155"
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
