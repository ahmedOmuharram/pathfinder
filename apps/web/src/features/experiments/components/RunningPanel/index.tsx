import { BarChart3, Check, Circle, FlaskConical, Loader2, X } from "lucide-react";
import { Card, CardContent } from "@/lib/components/ui/Card";
import { Button } from "@/lib/components/ui/Button";
import { Badge } from "@/lib/components/ui/Badge";
import { Progress } from "@/lib/components/ui/Progress";
import { useExperimentStore } from "../../store";
import type { PlanStepNode } from "@pathfinder/shared";
import { PHASE_LABELS, STEP_ANALYSIS_PHASE_LABELS } from "./constants";
import { MiniTreeView } from "./MiniTreeView";
import { StepAnalysisDetailPanel } from "./StepAnalysisDetailPanel";
import { OptimizationChart } from "./OptimizationChart";

export function RunningPanel() {
  const {
    progress,
    trialHistory,
    hasOptimization,
    cancelExperiment,
    runningConfig,
    stepAnalysisItems,
  } = useExperimentStore();

  const tp = progress?.trialProgress;

  const totalTrials = tp?.totalTrials ?? 0;
  const currentTrial = tp?.currentTrial ?? 0;
  const isStepAnalysis =
    runningConfig?.enableStepAnalysis === true || progress?.phase === "step_analysis";
  const isOptimizing = progress?.phase === "optimizing" && totalTrials > 0;
  const bestScore = tp?.bestTrial?.score;

  const saProgress = progress?.stepAnalysisProgress;

  // Step Analysis layout: full-width card with phase stepper + detail panel
  if (isStepAnalysis && progress?.phase === "step_analysis") {
    const saPhase = saProgress?.phase ?? "";
    const saCurrent = saProgress?.current ?? 0;
    const saTotal = saProgress?.total ?? 0;
    const saMessage = saProgress?.message ?? progress?.message ?? "Analyzing...";

    const PHASE_ORDER = [
      "step_evaluation",
      "operator_comparison",
      "contribution",
      "sensitivity",
    ] as const;

    const activeIdx = PHASE_ORDER.indexOf(saPhase as (typeof PHASE_ORDER)[number]);

    return (
      <div
        data-testid="running-panel"
        className="flex h-full min-h-0 flex-col p-6 animate-fade-in"
      >
        <Card className="flex min-h-0 w-full flex-1 flex-col overflow-hidden shadow-md">
          <CardContent className="flex min-h-0 flex-1 flex-col overflow-hidden p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FlaskConical className="h-6 w-6 animate-pulse text-primary" />
                <h2
                  data-testid="phase-label"
                  className="text-base font-semibold text-foreground"
                >
                  Analyzing Strategy
                </h2>
              </div>
              <Button
                data-testid="cancel-experiment-btn"
                variant="outline"
                size="sm"
                onClick={cancelExperiment}
                className="hover:border-destructive hover:text-destructive"
              >
                <X className="h-3.5 w-3.5" />
                Cancel
              </Button>
            </div>

            {/* Phase stepper */}
            <div className="mt-5 flex items-start gap-0">
              {PHASE_ORDER.map((phase, i) => {
                const idx = PHASE_ORDER.indexOf(phase);
                const isComplete = activeIdx > idx;
                const isActive = activeIdx === idx;
                const isPending = activeIdx < idx;
                return (
                  <div key={phase} className="flex flex-1 flex-col items-center">
                    <div className="flex w-full items-center">
                      {i > 0 && (
                        <div
                          className={`h-0.5 flex-1 transition-colors ${
                            isComplete || isActive ? "bg-primary" : "bg-border"
                          }`}
                        />
                      )}
                      <div
                        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
                          isComplete
                            ? "border-primary bg-primary text-primary-foreground"
                            : isActive
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-border bg-muted text-muted-foreground"
                        }`}
                      >
                        {isComplete ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : isActive ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Circle className="h-2.5 w-2.5" />
                        )}
                      </div>
                      {i < PHASE_ORDER.length - 1 && (
                        <div
                          className={`h-0.5 flex-1 transition-colors ${
                            isComplete ? "bg-primary" : "bg-border"
                          }`}
                        />
                      )}
                    </div>
                    <span
                      className={`mt-1.5 text-center text-[10px] leading-tight ${
                        isActive
                          ? "font-semibold text-primary"
                          : isPending
                            ? "text-muted-foreground/60"
                            : "font-medium text-foreground"
                      }`}
                    >
                      {STEP_ANALYSIS_PHASE_LABELS[phase]}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Sub-phase progress bar */}
            {saTotal > 0 && (
              <div className="mt-4">
                <Progress value={saCurrent} max={saTotal} />
                <div className="mt-1 flex justify-between text-xs text-muted-foreground">
                  <span>
                    {saCurrent} / {saTotal}
                  </span>
                  <span>{STEP_ANALYSIS_PHASE_LABELS[saPhase] ?? saPhase}</span>
                </div>
              </div>
            )}

            {/* Per-phase detail panel */}
            <div className="mt-4 flex min-h-0 flex-1 flex-col overflow-hidden">
              <StepAnalysisDetailPanel
                activePhase={saPhase}
                items={stepAnalysisItems}
                message={saMessage}
              />
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Standard layout (evaluation or single-step optimization)
  return (
    <div
      data-testid="running-panel"
      className="flex h-full items-center justify-center p-6 animate-fade-in"
    >
      <Card className={`w-full shadow-md ${isOptimizing ? "max-w-3xl" : "max-w-2xl"}`}>
        <CardContent className="p-6">
          <div className="text-center">
            {hasOptimization ? (
              <FlaskConical className="mx-auto h-10 w-10 animate-pulse text-primary" />
            ) : (
              <BarChart3 className="mx-auto h-10 w-10 animate-pulse text-primary" />
            )}
            <h2 className="mt-3 text-lg font-semibold text-foreground">
              {hasOptimization ? "Running Experiment" : "Evaluating Strategy"}
            </h2>
            {progress && (
              <Badge
                data-testid="phase-label"
                variant="secondary"
                className="mt-2 text-xs"
              >
                {PHASE_LABELS[progress.phase] ?? progress.phase}
              </Badge>
            )}
            {progress?.message && !isOptimizing && (
              <div className="mt-2 text-sm text-muted-foreground">
                {progress.message}
              </div>
            )}
          </div>

          {runningConfig?.stepTree && (
            <div className="mt-4">
              <MiniTreeView tree={runningConfig.stepTree as PlanStepNode} />
            </div>
          )}

          {isOptimizing && (
            <div className="mt-4 space-y-3">
              <div>
                <Progress value={currentTrial} max={totalTrials} />
                <div className="mt-1.5 flex justify-between text-xs text-muted-foreground">
                  <span>
                    Trial {currentTrial} / {totalTrials}
                  </span>
                  {bestScore != null && (
                    <span>
                      Best:{" "}
                      <span className="font-mono font-medium text-primary">
                        {bestScore.toFixed(4)}
                      </span>
                    </span>
                  )}
                </div>
              </div>
              {trialHistory.length > 1 && <OptimizationChart trials={trialHistory} />}
              {tp?.trial && (
                <div className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-left text-xs text-muted-foreground">
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

          {progress && !isOptimizing && (
            <div className="mt-4 space-y-3">
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

          <div className="mt-5 text-center">
            <Button
              data-testid="cancel-experiment-btn"
              variant="outline"
              size="sm"
              onClick={cancelExperiment}
              className="hover:border-destructive hover:text-destructive"
            >
              <X className="h-3.5 w-3.5" />
              Cancel
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
