import { FlaskConical, Loader2, X } from "lucide-react";
import { useExperimentStore, type TrialHistoryEntry } from "../store";

const PHASE_LABELS: Record<string, string> = {
  started: "Initializing...",
  optimizing: "Optimizing parameters...",
  evaluating: "Running evaluation...",
  cross_validating: "Cross-validating...",
  enriching: "Running enrichment...",
  completed: "Complete",
  error: "Error",
};

function OptimizationChart({ trials }: { trials: TrialHistoryEntry[] }) {
  const W = 360;
  const H = 120;
  const PAD = { top: 12, right: 12, bottom: 20, left: 36 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const maxScore = Math.max(...trials.map((t) => Math.max(t.score, t.bestScore)), 0.01);
  const minScore = Math.min(...trials.map((t) => Math.min(t.score, t.bestScore)), 0);
  const range = maxScore - minScore || 0.01;

  const x = (i: number) => PAD.left + (i / Math.max(trials.length - 1, 1)) * plotW;
  const y = (v: number) => PAD.top + plotH - ((v - minScore) / range) * plotH;

  const scoreLine = trials
    .map((t, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(t.score).toFixed(1)}`)
    .join(" ");
  const bestLine = trials
    .map(
      (t, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(t.bestScore).toFixed(1)}`,
    )
    .join(" ");

  const yTicks = [minScore, minScore + range / 2, maxScore];

  return (
    <div className="mx-auto w-full max-w-sm">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
        {yTicks.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              y1={y(v)}
              x2={W - PAD.right}
              y2={y(v)}
              stroke="#e2e8f0"
              strokeWidth={0.5}
            />
            <text
              x={PAD.left - 4}
              y={y(v) + 3}
              textAnchor="end"
              className="fill-slate-400"
              style={{ fontSize: 8 }}
            >
              {v.toFixed(2)}
            </text>
          </g>
        ))}
        <path
          d={scoreLine}
          fill="none"
          stroke="#94a3b8"
          strokeWidth={1}
          opacity={0.5}
        />
        {trials.map((t, i) => (
          <circle
            key={`s${i}`}
            cx={x(i)}
            cy={y(t.score)}
            r={2}
            className="fill-slate-400"
          />
        ))}
        <path d={bestLine} fill="none" stroke="#6366f1" strokeWidth={1.5} />
        {trials.length > 0 && (
          <circle
            cx={x(trials.length - 1)}
            cy={y(trials[trials.length - 1].bestScore)}
            r={3}
            className="fill-indigo-500"
          />
        )}
        <text
          x={PAD.left + plotW / 2}
          y={H - 2}
          textAnchor="middle"
          className="fill-slate-400"
          style={{ fontSize: 8 }}
        >
          Trial
        </text>
      </svg>
      <div className="flex justify-center gap-4 text-[9px] text-slate-400">
        <span className="flex items-center gap-1">
          <span className="inline-block h-1.5 w-3 rounded-full bg-indigo-500" /> Best
          score
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-1.5 w-3 rounded-full bg-slate-400 opacity-50" />{" "}
          Trial score
        </span>
      </div>
    </div>
  );
}

export function RunningPanel() {
  const { progress, trialHistory, cancelExperiment } = useExperimentStore();

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tp = (progress as any)?.trialProgress as
    | {
        totalTrials?: number;
        currentTrial?: number;
        bestTrial?: { score: number } | null;
        trial?: {
          trialNumber: number;
          score: number;
          recall?: number | null;
          resultCount?: number | null;
        } | null;
      }
    | undefined;

  const totalTrials = tp?.totalTrials ?? 0;
  const currentTrial = tp?.currentTrial ?? 0;
  const optimizationFraction = totalTrials > 0 ? currentTrial / totalTrials : 0;

  return (
    <div className="flex h-full items-center justify-center">
      <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white p-6 text-center">
        <FlaskConical className="mx-auto h-10 w-10 animate-pulse text-indigo-500" />
        <h2 className="mt-3 text-base font-semibold text-slate-800">
          Running Experiment
        </h2>
        {progress && (
          <div className="mt-3 space-y-3">
            <div className="text-[12px] font-medium text-slate-600">
              {PHASE_LABELS[progress.phase] ?? progress.phase}
            </div>
            {progress.message && (
              <div className="text-[11px] text-slate-500">{progress.message}</div>
            )}

            {progress.phase === "optimizing" && totalTrials > 0 && (
              <div className="space-y-3">
                <div className="mx-auto w-full max-w-xs">
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-indigo-500 transition-all duration-300"
                      style={{ width: `${optimizationFraction * 100}%` }}
                    />
                  </div>
                  <div className="mt-1 flex justify-between text-[10px] text-slate-400">
                    <span>
                      Trial {currentTrial} / {totalTrials}
                    </span>
                    {tp?.bestTrial && (
                      <span>
                        Best:{" "}
                        <span className="font-medium text-indigo-600">
                          {tp.bestTrial.score.toFixed(4)}
                        </span>
                      </span>
                    )}
                  </div>
                </div>

                {trialHistory.length > 1 && <OptimizationChart trials={trialHistory} />}

                {tp?.trial && (
                  <div className="mx-auto max-w-xs rounded border border-slate-100 bg-slate-50 px-3 py-2 text-left text-[10px] text-slate-600">
                    <div className="mb-1 font-semibold text-slate-700">
                      Latest trial #{tp.trial.trialNumber}
                    </div>
                    <div className="flex gap-4">
                      <span>
                        Score:{" "}
                        <span className="font-mono">{tp.trial.score.toFixed(4)}</span>
                      </span>
                      {tp.trial.recall != null && (
                        <span>
                          Recall:{" "}
                          <span className="font-mono">
                            {tp.trial.recall.toFixed(4)}
                          </span>
                        </span>
                      )}
                      {tp.trial.resultCount != null && (
                        <span>
                          Results:{" "}
                          <span className="font-mono">{tp.trial.resultCount}</span>
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {progress.cvFoldIndex != null && progress.cvTotalFolds != null && (
              <div className="mx-auto h-1.5 w-48 overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full rounded-full bg-indigo-500 transition-all duration-300"
                  style={{
                    width: `${((progress.cvFoldIndex + 1) / progress.cvTotalFolds) * 100}%`,
                  }}
                />
              </div>
            )}

            {progress.error && (
              <div className="rounded-md border border-red-100 bg-red-50 px-3 py-2 text-left text-[11px] text-red-700">
                {progress.error}
              </div>
            )}
          </div>
        )}
        {!progress && (
          <div className="mt-3 flex items-center justify-center gap-2 text-[12px] text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Connecting...
          </div>
        )}
        <button
          type="button"
          onClick={cancelExperiment}
          className="mt-4 inline-flex items-center gap-1 rounded-md border border-slate-200 px-3 py-1.5 text-[11px] font-medium text-slate-600 transition hover:border-red-300 hover:bg-red-50 hover:text-red-600"
        >
          <X className="h-3 w-3" />
          Cancel
        </button>
      </div>
    </div>
  );
}
