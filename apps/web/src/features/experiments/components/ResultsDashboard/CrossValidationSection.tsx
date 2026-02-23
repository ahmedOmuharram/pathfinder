import { useState, useMemo } from "react";
import type { CrossValidationResult } from "@pathfinder/shared";
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
import { pct, fmtNum } from "./utils";

interface CrossValidationSectionProps {
  cv: CrossValidationResult;
}

function SummaryCell({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="px-5 py-3">
      <div className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold tabular-nums text-slate-900">
        {value}
      </div>
      {sub && <div className="mt-0.5 text-[11px] text-slate-400">{sub}</div>}
    </div>
  );
}

export function CrossValidationSection({ cv }: CrossValidationSectionProps) {
  const [showFolds, setShowFolds] = useState(false);

  const foldChartData = useMemo(
    () =>
      cv.folds.map((f) => ({
        fold: `Subset ${f.foldIndex + 1}`,
        F1: +(f.metrics.f1Score * 100).toFixed(1),
        Sensitivity: +(f.metrics.sensitivity * 100).toFixed(1),
        Specificity: +(f.metrics.specificity * 100).toFixed(1),
      })),
    [cv.folds],
  );

  const riskLabel =
    cv.overfittingLevel === "low"
      ? "Low"
      : cv.overfittingLevel === "moderate"
        ? "Moderate"
        : "High";

  return (
    <Section title={`Control Robustness Analysis (${cv.k} subsets)`}>
      <div className="space-y-4">
        <p className="text-[11px] text-slate-500">
          Your controls were split into {cv.k} random subsets and each was evaluated
          independently. Consistent metrics across subsets indicate a robust,
          representative control set. High variance suggests the controls may be too few
          or biased toward particular genes.
        </p>

        <div className="rounded-lg border border-slate-200 bg-white">
          <div className="grid grid-cols-4 divide-x divide-slate-200">
            <SummaryCell
              label="Variance Risk"
              value={riskLabel}
              sub={`${(cv.overfittingScore * 100).toFixed(1)}% metric gap`}
            />
            <SummaryCell
              label="Mean F1"
              value={pct(cv.meanMetrics.f1Score)}
              sub={
                cv.stdMetrics.f1Score != null
                  ? `\u00b1 ${pct(cv.stdMetrics.f1Score)}`
                  : undefined
              }
            />
            <SummaryCell
              label="Mean Sensitivity"
              value={pct(cv.meanMetrics.sensitivity)}
              sub={
                cv.stdMetrics.sensitivity != null
                  ? `\u00b1 ${pct(cv.stdMetrics.sensitivity)}`
                  : undefined
              }
            />
            <SummaryCell
              label="Mean Specificity"
              value={pct(cv.meanMetrics.specificity)}
              sub={
                cv.stdMetrics.specificity != null
                  ? `\u00b1 ${pct(cv.stdMetrics.specificity)}`
                  : undefined
              }
            />
          </div>
        </div>

        {cv.folds.length > 1 && (
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <div className="mb-3 text-xs font-medium text-slate-500">
              Per-Subset Performance (%)
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart
                data={foldChartData}
                margin={{ top: 0, right: 0, left: -10, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#f1f5f9"
                  vertical={false}
                />
                <XAxis
                  dataKey="fold"
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                  axisLine={{ stroke: "#e2e8f0" }}
                  tickLine={false}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    fontSize: 11,
                    border: "1px solid #e2e8f0",
                    borderRadius: 6,
                    boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
                  }}
                />
                <Bar dataKey="F1" fill="#1e293b" radius={[2, 2, 0, 0]} barSize={14} />
                <Bar
                  dataKey="Sensitivity"
                  fill="#64748b"
                  radius={[2, 2, 0, 0]}
                  barSize={14}
                />
                <Bar
                  dataKey="Specificity"
                  fill="#cbd5e1"
                  radius={[2, 2, 0, 0]}
                  barSize={14}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        <button
          type="button"
          onClick={() => setShowFolds(!showFolds)}
          className="text-xs text-slate-400 transition hover:text-slate-600"
        >
          {showFolds ? "Hide subset details" : "Show subset details"}
        </button>

        {showFolds && (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-[10px] uppercase tracking-wider text-slate-400">
                  <th className="px-4 py-2.5 font-medium">Subset</th>
                  <th className="px-4 py-2.5 font-medium">Sensitivity</th>
                  <th className="px-4 py-2.5 font-medium">Specificity</th>
                  <th className="px-4 py-2.5 font-medium">F1</th>
                  <th className="px-4 py-2.5 font-medium">MCC</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cv.folds.map((fold) => (
                  <tr key={fold.foldIndex}>
                    <td className="px-4 py-2 text-slate-500">{fold.foldIndex + 1}</td>
                    <td className="px-4 py-2 font-mono tabular-nums text-slate-700">
                      {pct(fold.metrics.sensitivity)}
                    </td>
                    <td className="px-4 py-2 font-mono tabular-nums text-slate-700">
                      {pct(fold.metrics.specificity)}
                    </td>
                    <td className="px-4 py-2 font-mono tabular-nums text-slate-700">
                      {pct(fold.metrics.f1Score)}
                    </td>
                    <td className="px-4 py-2 font-mono tabular-nums text-slate-700">
                      {fmtNum(fold.metrics.mcc)}
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
