import { useMemo, useState } from "react";
import type { OptimizationProgressData, OptimizationTrial } from "@pathfinder/shared";
import { X, FlaskConical, Check, ChevronDown, ChevronRight } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
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
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${w}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

// Score chart (recharts)

interface ScoreChartDatum {
  trial: number;
  score: number;
  bestSoFar: number;
}

const CHART_HEIGHT = 320;

function buildTrialTicks(totalTrials: number): number[] {
  if (totalTrials <= 0) return [0];
  if (totalTrials <= 12) {
    return Array.from({ length: totalTrials + 1 }, (_, i) => i);
  }
  const step = Math.ceil(totalTrials / 10);
  const ticks: number[] = [];
  for (let t = 0; t <= totalTrials; t += step) ticks.push(t);
  if (ticks[ticks.length - 1] !== totalTrials) ticks.push(totalTrials);
  return ticks;
}

function ScoreChart({
  trials,
  totalTrials,
  currentTrial,
  isDone,
}: {
  trials: OptimizationTrial[];
  totalTrials: number;
  currentTrial: number;
  isDone: boolean;
}) {
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

  const effectiveTotal = Math.max(
    1,
    totalTrials,
    chartData[chartData.length - 1]?.trial ?? 1,
  );
  const stopTrial = Math.max(
    0,
    Math.min(
      effectiveTotal,
      Math.max(currentTrial, chartData[chartData.length - 1]?.trial ?? 0),
    ),
  );
  const hasEarlyStop = isDone && stopTrial < effectiveTotal;
  const trialTicks = buildTrialTicks(effectiveTotal);

  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Score progression
      </div>
      <div className="rounded border border-border bg-muted px-1 py-1">
        <div
          style={{
            width: "100%",
            height: CHART_HEIGHT,
            contain: "size layout",
            overflow: "hidden",
          }}
        >
          <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
            <LineChart
              data={chartData}
              margin={{ top: 4, right: 8, bottom: 0, left: 8 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis
                type="number"
                dataKey="trial"
                domain={[0, effectiveTotal]}
                ticks={trialTicks}
                allowDataOverflow
                tick={{ fontSize: 9, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="number"
                domain={[0, 1]}
                ticks={[0, 0.25, 0.5, 0.75, 1]}
                tick={{ fontSize: 9, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={false}
                width={32}
              />
              {hasEarlyStop ? (
                <>
                  <ReferenceArea
                    x1={stopTrial}
                    x2={effectiveTotal}
                    fill="#e2e8f0"
                    fillOpacity={0.45}
                  />
                  <ReferenceLine
                    x={stopTrial}
                    stroke="#64748b"
                    strokeDasharray="4 4"
                    ifOverflow="visible"
                  />
                </>
              ) : null}
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
      </div>
      <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-3 bg-muted-foreground" /> per-trial
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-3 bg-primary" /> best so far
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
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
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
                className={`border-b border-border last:border-0 ${isPareto ? "bg-primary/5" : ""}`}
              >
                <td className="px-1.5 py-1 tabular-nums text-muted-foreground">
                  {t.trialNumber}
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

// Collapsible trial section (collapsed by default)

function CollapsibleTrialSection({
  displayTrials,
  allTrialsCount,
  recentTrialsCount,
  paramNames,
  paretoTrialNumbers,
}: {
  displayTrials: OptimizationTrial[];
  allTrialsCount: number;
  recentTrialsCount: number;
  paramNames: string[];
  paretoTrialNumbers: Set<number>;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="mb-1 flex w-full items-center gap-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground transition-colors duration-150 hover:text-foreground"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <span>Recent trials</span>
        {allTrialsCount > recentTrialsCount ? (
          <span className="ml-auto font-normal normal-case tracking-normal text-muted-foreground">
            Showing last {recentTrialsCount} of {allTrialsCount} trials
          </span>
        ) : null}
      </button>
      {expanded && (
        <TrialTable
          trials={displayTrials}
          paramNames={paramNames}
          paretoTrialNumbers={paretoTrialNumbers}
        />
      )}
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

  const chartTrials = data.allTrials ?? data.recentTrials ?? [];
  const displayTrials = data.recentTrials ?? data.allTrials ?? [];

  const paretoTrialNumbers = new Set(
    (data.paretoFrontier ?? []).map((t) => t.trialNumber),
  );

  return (
    <div className="flex animate-fade-in justify-start">
      <div data-testid="optimization-panel" className="w-[760px] max-w-full">
        <div className="rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <div className="flex items-center gap-2">
              {isRunning ? (
                <FlaskConical className="h-4 w-4 animate-pulse text-primary" />
              ) : isComplete ? (
                <Check className="h-4 w-4 text-success" />
              ) : (
                <FlaskConical className="h-4 w-4 text-muted-foreground" />
              )}
              <span className="text-xs font-semibold text-foreground">
                {isRunning
                  ? "Parameter Optimisation"
                  : isComplete
                    ? "Optimisation Complete"
                    : isCancelled
                      ? "Optimisation Cancelled"
                      : "Optimisation Error"}
              </span>
              {isDone && data.totalTimeSeconds != null && (
                <span className="text-xs text-muted-foreground">
                  {fmtTime(data.totalTimeSeconds)}
                </span>
              )}
            </div>
            {isRunning && onCancel && (
              <button
                type="button"
                onClick={onCancel}
                className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-destructive/30 hover:bg-destructive/5 hover:text-destructive"
                title="Cancel optimisation"
              >
                <X className="h-3 w-3" />
                Cancel
              </button>
            )}
          </div>

          <div className="space-y-3 px-3 py-2.5 text-sm text-foreground">
            {data.searchName && (
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs text-muted-foreground">
                <span>
                  Search:{" "}
                  <span className="font-medium text-foreground">{data.searchName}</span>
                </span>
                {data.recordType && (
                  <span>
                    Record type:{" "}
                    <span className="font-medium text-foreground">
                      {data.recordType}
                    </span>
                  </span>
                )}
                {data.objective && (
                  <span>
                    Objective:{" "}
                    <span className="font-medium text-foreground">
                      {data.objective.toUpperCase()}
                    </span>
                  </span>
                )}
                {data.positiveControlsCount != null && (
                  <span>
                    +controls:{" "}
                    <span className="font-medium text-foreground">
                      {data.positiveControlsCount}
                    </span>
                  </span>
                )}
                {data.negativeControlsCount != null && (
                  <span>
                    -controls:{" "}
                    <span className="font-medium text-foreground">
                      {data.negativeControlsCount}
                    </span>
                  </span>
                )}
              </div>
            )}

            {(isRunning || isDone) && (
              <div>
                <div className="mb-1 flex items-baseline justify-between text-xs">
                  <span className="text-muted-foreground">
                    Trial {current} of {total}
                  </span>
                  <span className="tabular-nums text-muted-foreground">
                    {progressPct.toFixed(0)}%
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      isComplete
                        ? "bg-success"
                        : isCancelled || isError
                          ? "bg-amber-400"
                          : "bg-primary"
                    }`}
                    style={{ width: `${progressPct}%` }}
                  />
                </div>
              </div>
            )}

            {data.bestTrial && (
              <div className="rounded-md border border-success/30 bg-success/10 px-2.5 py-2">
                <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-success">
                  Best configuration (trial {data.bestTrial.trialNumber})
                </div>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                  {paramNames.map((n) => (
                    <span key={n}>
                      <span className="text-muted-foreground">{n}:</span>{" "}
                      <span className="font-medium tabular-nums">
                        {typeof data.bestTrial!.parameters[n] === "number"
                          ? fmt(data.bestTrial!.parameters[n] as number, 4)
                          : String(data.bestTrial!.parameters[n] ?? "--")}
                      </span>
                    </span>
                  ))}
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                  <span>
                    <span className="text-muted-foreground">Score:</span>{" "}
                    <span className="font-semibold tabular-nums text-success">
                      {fmt(data.bestTrial.score, 4)}
                    </span>
                  </span>
                  <span>
                    <span className="text-muted-foreground">Recall:</span>{" "}
                    <span className="tabular-nums">{pct(data.bestTrial.recall)}</span>
                  </span>
                  <span>
                    <span className="text-muted-foreground">FPR:</span>{" "}
                    <span className="tabular-nums">
                      {pct(data.bestTrial.falsePositiveRate)}
                    </span>
                  </span>
                  {data.bestTrial.positiveHits != null && (
                    <span>
                      <span className="text-muted-foreground">+Hits:</span>{" "}
                      <span className="tabular-nums">
                        {data.bestTrial.positiveHits}/
                        {data.bestTrial.totalPositives ?? "?"}
                      </span>
                    </span>
                  )}
                  {data.bestTrial.negativeHits != null && (
                    <span>
                      <span className="text-muted-foreground">-Hits:</span>{" "}
                      <span className="tabular-nums">
                        {data.bestTrial.negativeHits}/
                        {data.bestTrial.totalNegatives ?? "?"}
                      </span>
                    </span>
                  )}
                  {data.bestTrial.resultCount != null && (
                    <span>
                      <span className="text-muted-foreground">Results:</span>{" "}
                      <span className="tabular-nums">{data.bestTrial.resultCount}</span>
                    </span>
                  )}
                </div>
              </div>
            )}

            {isError && data.error && (
              <div className="rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-2 text-xs text-destructive">
                {data.error}
              </div>
            )}

            {chartTrials.length >= 2 && (
              <ScoreChart
                trials={chartTrials}
                totalTrials={total}
                currentTrial={current}
                isDone={isDone}
              />
            )}

            {isDone && data.sensitivity && Object.keys(data.sensitivity).length > 0 && (
              <div>
                <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Parameter sensitivity
                </div>
                <div className="space-y-1">
                  {Object.entries(data.sensitivity)
                    .sort(([, a], [, b]) => b - a)
                    .map(([name, value]) => (
                      <div key={name} className="flex items-center gap-2 text-xs">
                        <span className="w-28 truncate text-muted-foreground">
                          {name}
                        </span>
                        <SensitivityBar value={value} />
                      </div>
                    ))}
                </div>
              </div>
            )}

            {displayTrials.length > 0 && (
              <CollapsibleTrialSection
                displayTrials={displayTrials}
                allTrialsCount={data.allTrials?.length ?? 0}
                recentTrialsCount={data.recentTrials?.length ?? 0}
                paramNames={paramNames}
                paretoTrialNumbers={paretoTrialNumbers}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
