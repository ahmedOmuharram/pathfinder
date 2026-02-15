import { useMemo, useState } from "react";
import type { OptimizationProgressData, OptimizationTrial } from "@pathfinder/shared";
import { ChevronDown, ChevronUp, X, FlaskConical, Check } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

// Helpers

function pct(value: number | null | undefined): string {
  if (value == null) return "--";
  return `${(value * 100).toFixed(1)}%`;
}

function fmt(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "--";
  return value.toFixed(decimals);
}

function fmtTime(seconds: number | undefined): string {
  if (seconds == null) return "--";
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function SensitivityBar({ value }: { value: number }) {
  const w = Math.max(0, Math.min(100, value * 100));
  const label = value >= 0.6 ? "High" : value >= 0.3 ? "Medium" : "Low";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all duration-300"
          style={{ width: `${w}%` }}
        />
      </div>
      <span className="text-[10px] text-slate-500">{label}</span>
    </div>
  );
}

// Score chart (recharts)

interface ScoreChartDatum {
  trial: number;
  score: number;
  bestSoFar: number;
}

function ScoreChart({ trials }: { trials: OptimizationTrial[] }) {
  const chartData = useMemo<ScoreChartDatum[]>(() => {
    if (trials.length < 2) return [];

    let best = -Infinity;
    return trials.map((t) => {
      best = Math.max(best, t.score);
      return {
        trial: t.trialNumber,
        score: parseFloat(t.score.toFixed(4)),
        bestSoFar: parseFloat(best.toFixed(4)),
      };
    });
  }, [trials]);

  if (chartData.length < 2) return null;

  return (
    <div>
      <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        Score progression
      </div>
      <div className="rounded border border-slate-200 bg-slate-50 px-1 py-1">
        <ResponsiveContainer width="100%" height={320}>
          <LineChart
            data={chartData}
            margin={{ top: 4, right: 8, bottom: 0, left: -16 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis
              dataKey="trial"
              tick={{ fontSize: 9, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              domain={[0, "auto"]}
              tick={{ fontSize: 9, fill: "#94a3b8" }}
              tickLine={false}
              axisLine={false}
              width={32}
            />
            <RechartsTooltip
              contentStyle={{
                fontSize: 11,
                padding: "4px 8px",
                borderRadius: 6,
                border: "1px solid #e2e8f0",
              }}
              labelFormatter={(v) => `Trial ${v}`}
              formatter={(value: number | undefined, name: string | undefined) => [
                value != null ? value.toFixed(4) : "--",
                name === "score" ? "Score" : "Best so far",
              ]}
            />
            <Line
              type="monotone"
              dataKey="score"
              stroke="#94a3b8"
              strokeWidth={1}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="stepAfter"
              dataKey="bestSoFar"
              stroke="#6366f1"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex gap-3 text-[9px] text-slate-400">
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-3 bg-slate-400" /> per-trial
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-3 bg-indigo-500" /> best so far
        </span>
      </div>
    </div>
  );
}

// Trial table

function TrialTable({
  trials,
  paramNames,
  paretoTrialNumbers,
}: {
  trials: OptimizationTrial[];
  paramNames: string[];
  paretoTrialNumbers?: Set<number>;
}) {
  if (trials.length === 0) return null;

  const hasPositiveHits = trials.some((t) => t.positiveHits != null);
  const hasNegativeHits = trials.some((t) => t.negativeHits != null);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-[11px]">
        <thead>
          <tr className="border-b border-slate-200 text-[10px] uppercase tracking-wider text-slate-500">
            <th className="px-1.5 py-1">#</th>
            {paramNames.map((n) => (
              <th key={n} className="px-1.5 py-1 font-medium">
                {n}
              </th>
            ))}
            <th className="px-1.5 py-1">Score</th>
            <th className="px-1.5 py-1">Recall</th>
            <th className="px-1.5 py-1">FPR</th>
            {hasPositiveHits && <th className="px-1.5 py-1">+Hits</th>}
            {hasNegativeHits && <th className="px-1.5 py-1">-Hits</th>}
            <th className="px-1.5 py-1">Results</th>
          </tr>
        </thead>
        <tbody>
          {trials.map((t) => {
            const isPareto = paretoTrialNumbers?.has(t.trialNumber);
            return (
              <tr
                key={t.trialNumber}
                className={`border-b border-slate-100 last:border-0 ${isPareto ? "bg-indigo-50/50" : ""}`}
              >
                <td className="px-1.5 py-1 tabular-nums text-slate-500">
                  {t.trialNumber}
                  {isPareto && (
                    <span
                      className="ml-0.5 text-[9px] text-indigo-500"
                      title="Pareto optimal"
                    >
                      *
                    </span>
                  )}
                </td>
                {paramNames.map((n) => (
                  <td key={n} className="px-1.5 py-1 tabular-nums">
                    {fmt(
                      typeof t.parameters[n] === "number"
                        ? (t.parameters[n] as number)
                        : null,
                      3,
                    ) === "--"
                      ? String(t.parameters[n] ?? "--")
                      : fmt(t.parameters[n] as number, 3)}
                  </td>
                ))}
                <td className="px-1.5 py-1 tabular-nums font-medium">
                  {fmt(t.score, 4)}
                </td>
                <td className="px-1.5 py-1 tabular-nums">{pct(t.recall)}</td>
                <td className="px-1.5 py-1 tabular-nums">{pct(t.falsePositiveRate)}</td>
                {hasPositiveHits && (
                  <td className="px-1.5 py-1 tabular-nums">
                    {t.positiveHits != null
                      ? `${t.positiveHits}/${t.totalPositives ?? "?"}`
                      : "--"}
                  </td>
                )}
                {hasNegativeHits && (
                  <td className="px-1.5 py-1 tabular-nums">
                    {t.negativeHits != null
                      ? `${t.negativeHits}/${t.totalNegatives ?? "?"}`
                      : "--"}
                  </td>
                )}
                <td className="px-1.5 py-1 tabular-nums">{t.resultCount ?? "--"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// Main component

interface OptimizationProgressPanelProps {
  data: OptimizationProgressData;
  onCancel?: () => void;
}

export function OptimizationProgressPanel({
  data,
  onCancel,
}: OptimizationProgressPanelProps) {
  const [showAllTrials, setShowAllTrials] = useState(false);

  const isRunning = data.status === "started" || data.status === "running";
  const isComplete = data.status === "completed";
  const isCancelled = data.status === "cancelled";
  const isError = data.status === "error";
  const isDone = isComplete || isCancelled || isError;

  const current = data.currentTrial ?? 0;
  const total = data.totalTrials ?? data.budget ?? 1;
  const progressPct = total > 0 ? (current / total) * 100 : 0;

  const paramNames =
    data.parameterSpace?.map((p) => p.name) ??
    (data.bestTrial ? Object.keys(data.bestTrial.parameters) : []);

  const displayTrials = showAllTrials
    ? (data.allTrials ?? data.recentTrials ?? [])
    : (data.recentTrials ?? []);

  const paretoTrialNumbers = new Set(
    (data.paretoFrontier ?? []).map((t) => t.trialNumber),
  );

  return (
    <div className="flex animate-fade-in justify-start">
      <div className="w-full max-w-[85%]">
        <div className="rounded-lg border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
            <div className="flex items-center gap-2">
              {isRunning ? (
                <FlaskConical className="h-4 w-4 animate-pulse text-indigo-500" />
              ) : isComplete ? (
                <Check className="h-4 w-4 text-emerald-500" />
              ) : (
                <FlaskConical className="h-4 w-4 text-slate-400" />
              )}
              <span className="text-xs font-semibold text-slate-700">
                {isRunning
                  ? "Parameter Optimisation"
                  : isComplete
                    ? "Optimisation Complete"
                    : isCancelled
                      ? "Optimisation Cancelled"
                      : "Optimisation Error"}
              </span>
              {isDone && data.totalTimeSeconds != null && (
                <span className="text-[10px] text-slate-400">
                  {fmtTime(data.totalTimeSeconds)}
                </span>
              )}
            </div>
            {isRunning && onCancel && (
              <button
                type="button"
                onClick={onCancel}
                className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600 transition-colors hover:border-red-300 hover:bg-red-50 hover:text-red-600"
                title="Cancel optimisation"
              >
                <X className="h-3 w-3" />
                Cancel
              </button>
            )}
          </div>

          <div className="space-y-3 px-3 py-2.5 text-[12px] text-slate-700">
            {data.searchName && (
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[11px] text-slate-500">
                <span>
                  Search:{" "}
                  <span className="font-medium text-slate-700">{data.searchName}</span>
                </span>
                {data.recordType && (
                  <span>
                    Record type:{" "}
                    <span className="font-medium text-slate-700">
                      {data.recordType}
                    </span>
                  </span>
                )}
                {data.objective && (
                  <span>
                    Objective:{" "}
                    <span className="font-medium text-slate-700">
                      {data.objective.toUpperCase()}
                    </span>
                  </span>
                )}
                {data.positiveControlsCount != null && (
                  <span>
                    +controls:{" "}
                    <span className="font-medium text-slate-700">
                      {data.positiveControlsCount}
                    </span>
                  </span>
                )}
                {data.negativeControlsCount != null && (
                  <span>
                    -controls:{" "}
                    <span className="font-medium text-slate-700">
                      {data.negativeControlsCount}
                    </span>
                  </span>
                )}
              </div>
            )}

            {(isRunning || isDone) && (
              <div>
                <div className="mb-1 flex items-baseline justify-between text-[11px]">
                  <span className="text-slate-500">
                    Trial {current} of {total}
                  </span>
                  <span className="tabular-nums text-slate-400">
                    {progressPct.toFixed(0)}%
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      isComplete
                        ? "bg-emerald-500"
                        : isCancelled || isError
                          ? "bg-amber-400"
                          : "bg-indigo-500"
                    }`}
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              </div>
            )}

            {data.bestTrial && (
              <div className="rounded-md border border-emerald-200 bg-emerald-50/50 px-2.5 py-2">
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
                  Best configuration (trial {data.bestTrial.trialNumber})
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
                  {paramNames.map((n) => (
                    <span key={n}>
                      <span className="text-slate-500">{n}:</span>{" "}
                      <span className="font-medium tabular-nums">
                        {typeof data.bestTrial!.parameters[n] === "number"
                          ? fmt(data.bestTrial!.parameters[n] as number, 4)
                          : String(data.bestTrial!.parameters[n] ?? "--")}
                      </span>
                    </span>
                  ))}
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
                  <span>
                    <span className="text-slate-500">Score:</span>{" "}
                    <span className="font-semibold tabular-nums text-emerald-700">
                      {fmt(data.bestTrial.score, 4)}
                    </span>
                  </span>
                  <span>
                    <span className="text-slate-500">Recall:</span>{" "}
                    <span className="tabular-nums">{pct(data.bestTrial.recall)}</span>
                  </span>
                  <span>
                    <span className="text-slate-500">FPR:</span>{" "}
                    <span className="tabular-nums">
                      {pct(data.bestTrial.falsePositiveRate)}
                    </span>
                  </span>
                  {data.bestTrial.positiveHits != null && (
                    <span>
                      <span className="text-slate-500">+Hits:</span>{" "}
                      <span className="tabular-nums">
                        {data.bestTrial.positiveHits}/
                        {data.bestTrial.totalPositives ?? "?"}
                      </span>
                    </span>
                  )}
                  {data.bestTrial.negativeHits != null && (
                    <span>
                      <span className="text-slate-500">-Hits:</span>{" "}
                      <span className="tabular-nums">
                        {data.bestTrial.negativeHits}/
                        {data.bestTrial.totalNegatives ?? "?"}
                      </span>
                    </span>
                  )}
                  {data.bestTrial.resultCount != null && (
                    <span>
                      <span className="text-slate-500">Results:</span>{" "}
                      <span className="tabular-nums">{data.bestTrial.resultCount}</span>
                    </span>
                  )}
                </div>
              </div>
            )}

            {isError && data.error && (
              <div className="rounded-md border border-red-200 bg-red-50 px-2.5 py-2 text-[11px] text-red-700">
                {data.error}
              </div>
            )}

            {(data.allTrials ?? data.recentTrials ?? []).length >= 2 && (
              <ScoreChart trials={data.allTrials ?? data.recentTrials ?? []} />
            )}

            {isDone && data.sensitivity && Object.keys(data.sensitivity).length > 0 && (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Parameter sensitivity
                </div>
                <div className="space-y-1">
                  {Object.entries(data.sensitivity)
                    .sort(([, a], [, b]) => b - a)
                    .map(([name, value]) => (
                      <div key={name} className="flex items-center gap-2 text-[11px]">
                        <span className="w-28 truncate text-slate-600">{name}</span>
                        <SensitivityBar value={value} />
                      </div>
                    ))}
                </div>
              </div>
            )}

            {isDone && data.paretoFrontier && data.paretoFrontier.length > 1 && (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Pareto frontier ({data.paretoFrontier.length} optimal)
                </div>
                <div className="text-[11px] text-slate-600">
                  Trials marked with{" "}
                  <span className="font-medium text-indigo-500">*</span> are
                  Pareto-optimal (best trade-off between recall and FPR).
                </div>
              </div>
            )}

            {displayTrials.length > 0 && (
              <div>
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    {showAllTrials ? "All trials" : "Recent trials"}
                  </span>
                  {isDone &&
                    (data.allTrials?.length ?? 0) >
                      (data.recentTrials?.length ?? 0) && (
                      <button
                        type="button"
                        onClick={() => setShowAllTrials((v) => !v)}
                        className="inline-flex items-center gap-0.5 text-[10px] text-slate-500 hover:text-slate-700"
                      >
                        {showAllTrials ? (
                          <>
                            Show recent <ChevronUp className="h-3 w-3" />
                          </>
                        ) : (
                          <>
                            Show all ({data.allTrials?.length}){" "}
                            <ChevronDown className="h-3 w-3" />
                          </>
                        )}
                      </button>
                    )}
                </div>
                <TrialTable
                  trials={displayTrials}
                  paramNames={paramNames}
                  paretoTrialNumbers={paretoTrialNumbers}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
