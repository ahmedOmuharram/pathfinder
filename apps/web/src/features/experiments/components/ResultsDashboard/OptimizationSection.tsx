import { useState, useMemo } from "react";
import type { OptimizationResult, OptimizationTrialResult } from "@pathfinder/shared";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Section } from "./Section";
import { pct } from "./utils";

interface OptimizationSectionProps {
  result: OptimizationResult;
}

export function OptimizationSection({ result }: OptimizationSectionProps) {
  const [showTrials, setShowTrials] = useState(false);

  const convergenceData = useMemo(() => {
    return result.allTrials.map((t: OptimizationTrialResult, i: number) => {
      const bestSoFar = Math.max(
        ...result.allTrials.slice(0, i + 1).map((x) => x.score),
      );
      return {
        trial: t.trialNumber,
        score: +(t.score * 100).toFixed(1),
        best: +(bestSoFar * 100).toFixed(1),
      };
    });
  }, [result.allTrials]);

  return (
    <Section title="Parameter Optimization">
      <div className="space-y-4">
        <div className="rounded-lg border border-border bg-card">
          <div className="grid grid-cols-3 divide-x divide-border">
            <div className="px-5 py-3">
              <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Best Score
              </div>
              <div className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                {result.bestTrial ? pct(result.bestTrial.score) : "\u2014"}
              </div>
            </div>
            <div className="px-5 py-3">
              <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Trials
              </div>
              <div className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                {result.totalTrials}
              </div>
            </div>
            <div className="px-5 py-3">
              <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Time
              </div>
              <div className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                {result.totalTimeSeconds.toFixed(1)}s
              </div>
            </div>
          </div>
        </div>

        {result.bestTrial && (
          <div className="rounded-lg border border-border bg-card">
            <div className="border-b border-border px-5 py-2.5 text-xs font-medium text-muted-foreground">
              Best Trial Parameters
            </div>
            <div className="divide-y divide-border/50">
              {Object.entries(result.bestTrial.parameters).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between px-5 py-2">
                  <span className="text-sm text-muted-foreground">{k}</span>
                  <span className="font-mono text-sm tabular-nums text-foreground">
                    {String(v)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {convergenceData.length > 1 && (
          <div className="rounded-lg border border-border bg-card p-5">
            <div className="mb-3 text-xs font-medium text-muted-foreground">
              Convergence
            </div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart
                data={convergenceData}
                margin={{ top: 0, right: 0, left: -10, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#f1f5f9"
                  vertical={false}
                />
                <XAxis
                  dataKey="trial"
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                  axisLine={{ stroke: "#e2e8f0" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    fontSize: 11,
                    border: "1px solid #e2e8f0",
                    borderRadius: 6,
                  }}
                />
                <Bar
                  dataKey="score"
                  fill="#cbd5e1"
                  radius={[2, 2, 0, 0]}
                  barSize={8}
                  name="Trial Score %"
                />
                <Bar
                  dataKey="best"
                  fill="#1e293b"
                  radius={[2, 2, 0, 0]}
                  barSize={8}
                  name="Best So Far %"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        <button
          type="button"
          onClick={() => setShowTrials(!showTrials)}
          className="text-xs text-muted-foreground transition hover:text-foreground"
        >
          {showTrials ? "Hide trial history" : "Show trial history"}
        </button>

        {showTrials && (
          <div className="max-h-60 overflow-x-auto overflow-y-auto rounded-lg border border-border bg-card">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-card">
                <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">#</th>
                  <th className="px-4 py-2.5 font-medium">Score</th>
                  <th className="px-4 py-2.5 font-medium">Recall</th>
                  <th className="px-4 py-2.5 font-medium">FPR</th>
                  <th className="px-4 py-2.5 font-medium">Results</th>
                  <th className="px-4 py-2.5 font-medium">Parameters</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {result.allTrials.map((t) => (
                  <tr
                    key={t.trialNumber}
                    className={
                      t.trialNumber === result.bestTrial?.trialNumber ? "bg-accent" : ""
                    }
                  >
                    <td className="px-4 py-2 text-muted-foreground">{t.trialNumber}</td>
                    <td className="px-4 py-2 font-mono tabular-nums text-foreground">
                      {pct(t.score)}
                    </td>
                    <td className="px-4 py-2 font-mono tabular-nums text-foreground">
                      {t.recall != null ? pct(t.recall) : "\u2014"}
                    </td>
                    <td className="px-4 py-2 font-mono tabular-nums text-foreground">
                      {t.falsePositiveRate != null
                        ? pct(t.falsePositiveRate)
                        : "\u2014"}
                    </td>
                    <td className="px-4 py-2 font-mono tabular-nums text-foreground">
                      {t.resultCount ?? "\u2014"}
                    </td>
                    <td className="max-w-xs truncate px-4 py-2 font-mono text-xs text-muted-foreground">
                      {Object.entries(t.parameters)
                        .map(([k, v]) => `${k}=${v}`)
                        .join(", ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Section>
  );
}
