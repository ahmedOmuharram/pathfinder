import type { OptimizationProgressData } from "@pathfinder/shared";
import { X, FlaskConical, Check } from "lucide-react";
import { Card } from "@/lib/components/ui/Card";
import {
  pct,
  fmt,
  fmtTime,
} from "@/features/chat/components/optimization/optimizationFormatters";
import { OptimizationChart } from "@/features/chat/components/optimization/OptimizationChart";
import { CollapsibleTrialSection } from "@/features/chat/components/optimization/OptimizationTrialList";

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
    data.parameterSpecs?.map((p: { name: string }) => p.name) ??
    (data.bestTrial?.parameters ? Object.keys(data.bestTrial.parameters) : []);

  const chartTrials = data.allTrials ?? data.recentTrials ?? [];
  const displayTrials = data.recentTrials ?? data.allTrials ?? [];

  const paretoTrialNumbers = new Set(
    (data.paretoFrontier ?? []).map((t) => t.trialNumber),
  );

  return (
    <div className="flex animate-fade-in justify-start">
      <div data-testid="optimization-panel" className="w-[760px] max-w-full">
        <Card>
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
                {(data as Record<string, unknown>)["positiveControlsCount"] != null && (
                  <span>
                    +controls:{" "}
                    <span className="font-medium text-foreground">
                      {String(
                        (data as Record<string, unknown>)["positiveControlsCount"],
                      )}
                    </span>
                  </span>
                )}
                {(data as Record<string, unknown>)["negativeControlsCount"] != null && (
                  <span>
                    -controls:{" "}
                    <span className="font-medium text-foreground">
                      {String(
                        (data as Record<string, unknown>)["negativeControlsCount"],
                      )}
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
                  {paramNames.map((n) => {
                    const params = data.bestTrial!.parameters ?? {};
                    return (
                      <span key={n}>
                        <span className="text-muted-foreground">{n}:</span>{" "}
                        <span className="font-medium tabular-nums">
                          {typeof params[n] === "number"
                            ? fmt(params[n] as number, 4)
                            : String(params[n] ?? "--")}
                        </span>
                      </span>
                    );
                  })}
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
              <OptimizationChart
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
        </Card>
      </div>
    </div>
  );
}
