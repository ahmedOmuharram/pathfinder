import { FlaskConical, Loader2, X } from "lucide-react";
import { Card, CardContent } from "@/lib/components/ui/Card";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import { Progress } from "@/lib/components/ui/Progress";
import { useExperimentStore, type TrialHistoryEntry } from "../store";

const PHASE_LABELS: Record<string, string> = {
  started: "Initializing",
  optimizing: "Optimizing parameters",
  evaluating: "Evaluating",
  cross_validating: "Cross-validating",
  enriching: "Computing enrichment",
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
              stroke="hsl(var(--border))"
              strokeWidth={0.5}
            />
            <text
              x={PAD.left - 4}
              y={y(v) + 3}
              textAnchor="end"
              fill="hsl(var(--muted-foreground))"
              style={{ fontSize: 8 }}
            >
              {v.toFixed(2)}
            </text>
          </g>
        ))}
        <path
          d={scoreLine}
          fill="none"
          stroke="hsl(var(--muted-foreground))"
          strokeWidth={1}
          opacity={0.5}
        />
        {trials.map((t, i) => (
          <circle
            key={`s${i}`}
            cx={x(i)}
            cy={y(t.score)}
            r={2}
            fill="hsl(var(--muted-foreground))"
          />
        ))}
        <path d={bestLine} fill="none" stroke="hsl(var(--primary))" strokeWidth={1.5} />
        {trials.length > 0 && (
          <circle
            cx={x(trials.length - 1)}
            cy={y(trials[trials.length - 1].bestScore)}
            r={3}
            fill="hsl(var(--primary))"
          />
        )}
        <text
          x={PAD.left + plotW / 2}
          y={H - 2}
          textAnchor="middle"
          fill="hsl(var(--muted-foreground))"
          style={{ fontSize: 8 }}
        >
          Trial
        </text>
      </svg>
      <div className="flex justify-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block h-1.5 w-3 rounded-full bg-primary" /> Best score
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-1.5 w-3 rounded-full bg-muted-foreground opacity-50" />{" "}
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
    <div className="flex h-full items-center justify-center animate-fade-in">
      <Card className="w-full max-w-lg shadow-md">
        <CardContent className="p-6 text-center">
          <FlaskConical className="mx-auto h-10 w-10 animate-pulse text-primary" />
          <h2 className="mt-3 text-lg font-semibold text-foreground">
            Running Experiment
          </h2>
          {progress && (
            <div className="mt-4 space-y-3">
              <Badge variant="secondary" className="text-xs">
                {PHASE_LABELS[progress.phase] ?? progress.phase}
              </Badge>
              {progress.message && (
                <div className="text-sm text-muted-foreground">{progress.message}</div>
              )}

              {progress.phase === "optimizing" && totalTrials > 0 && (
                <div className="space-y-3">
                  <div className="mx-auto w-full max-w-xs">
                    <Progress value={currentTrial} max={totalTrials} />
                    <div className="mt-1.5 flex justify-between text-xs text-muted-foreground">
                      <span>
                        Trial {currentTrial} / {totalTrials}
                      </span>
                      {tp?.bestTrial && (
                        <span>
                          Best:{" "}
                          <span className="font-mono font-medium text-primary">
                            {tp.bestTrial.score.toFixed(4)}
                          </span>
                        </span>
                      )}
                    </div>
                  </div>

                  {trialHistory.length > 1 && (
                    <OptimizationChart trials={trialHistory} />
                  )}

                  {tp?.trial && (
                    <div className="mx-auto max-w-xs rounded-lg border border-border bg-muted/50 px-3 py-2 text-left text-xs text-muted-foreground">
                      <div className="mb-1 font-semibold text-foreground">
                        Latest trial #{tp.trial.trialNumber}
                      </div>
                      <div className="flex gap-4 font-mono">
                        <span>Score: {tp.trial.score.toFixed(4)}</span>
                        {tp.trial.recall != null && (
                          <span>Recall: {tp.trial.recall.toFixed(4)}</span>
                        )}
                        {tp.trial.resultCount != null && (
                          <span>Results: {tp.trial.resultCount}</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {progress.cvFoldIndex != null && progress.cvTotalFolds != null && (
                <div className="mx-auto w-48">
                  <Progress
                    value={progress.cvFoldIndex + 1}
                    max={progress.cvTotalFolds}
                  />
                </div>
              )}

              {progress.error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-left text-sm text-destructive">
                  {progress.error}
                </div>
              )}
            </div>
          )}
          {!progress && (
            <div className="mt-4 flex items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Connecting...
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={cancelExperiment}
            className="mt-5 hover:border-destructive hover:text-destructive"
          >
            <X className="h-3.5 w-3.5" />
            Cancel
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
