import { ArrowRight, Check, Loader2 } from "lucide-react";
import { Badge } from "@/lib/components/ui/Badge";
import type { StepAnalysisLiveItems } from "../../store";
import { VERDICT_STYLE, STEP_ANALYSIS_PHASE_LABELS } from "./constants";

export function StepAnalysisDetailPanel({
  activePhase,
  items,
  message,
}: {
  activePhase: string;
  items: StepAnalysisLiveItems;
  message: string;
}) {
  const hasAny =
    items.evaluations.length > 0 ||
    items.operators.length > 0 ||
    items.contributions.length > 0 ||
    items.sensitivities.length > 0;

  if (!hasAny) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-lg border border-border bg-muted/20 px-4 py-6 text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        {message}
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
      {/* Phase 1: Per-Step Evaluation results */}
      {items.evaluations.length > 0 && (
        <div className="rounded-lg border border-border bg-muted/10 p-3">
          <div className="mb-2 text-xs font-semibold text-foreground">
            {STEP_ANALYSIS_PHASE_LABELS.step_evaluation}
            <Badge variant="secondary" className="ml-2 text-[10px]">
              {items.evaluations.length}
            </Badge>
          </div>
          <div className="space-y-1">
            {items.evaluations.map((ev) => (
              <div
                key={ev.stepId}
                className="flex items-center justify-between rounded-md bg-background px-3 py-1.5 text-xs"
              >
                <span
                  className="truncate font-medium text-foreground"
                  title={ev.searchName}
                >
                  {ev.displayName}
                </span>
                <div className="flex shrink-0 items-center gap-3 pl-3 font-mono text-muted-foreground">
                  <span>{ev.resultCount.toLocaleString()} results</span>
                  <span
                    className={
                      ev.recall >= 0.5 ? "text-green-600 dark:text-green-400" : ""
                    }
                  >
                    Recall {(ev.recall * 100).toFixed(0)}%
                  </span>
                  <span
                    className={
                      ev.falsePositiveRate > 0.2 ? "text-red-600 dark:text-red-400" : ""
                    }
                  >
                    FPR {(ev.falsePositiveRate * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Phase 2: Operator Comparison results */}
      {items.operators.length > 0 && (
        <div className="rounded-lg border border-border bg-muted/10 p-3">
          <div className="mb-2 text-xs font-semibold text-foreground">
            {STEP_ANALYSIS_PHASE_LABELS.operator_comparison}
            <Badge variant="secondary" className="ml-2 text-[10px]">
              {items.operators.length}
            </Badge>
          </div>
          <div className="space-y-1">
            {items.operators.map((oc) => {
              const changed = oc.recommendedOperator !== oc.currentOperator;
              return (
                <div
                  key={oc.combineNodeId}
                  className="flex items-center justify-between rounded-md bg-background px-3 py-1.5 text-xs"
                >
                  <span className="truncate font-medium text-foreground">
                    Node {oc.combineNodeId}
                  </span>
                  <div className="flex shrink-0 items-center gap-2 pl-3 font-mono">
                    <Badge variant="outline" className="text-[10px]">
                      {oc.currentOperator}
                    </Badge>
                    {changed && (
                      <>
                        <ArrowRight className="h-3 w-3 text-primary" />
                        <Badge className="bg-primary/10 text-[10px] text-primary">
                          {oc.recommendedOperator}
                        </Badge>
                      </>
                    )}
                    {!changed && <Check className="h-3 w-3 text-green-600" />}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Phase 3: Ablation / Step Contribution results */}
      {items.contributions.length > 0 && (
        <div className="rounded-lg border border-border bg-muted/10 p-3">
          <div className="mb-2 text-xs font-semibold text-foreground">
            {STEP_ANALYSIS_PHASE_LABELS.contribution}
            <Badge variant="secondary" className="ml-2 text-[10px]">
              {items.contributions.length}
            </Badge>
          </div>
          <div className="space-y-1">
            {items.contributions.map((sc) => {
              const vs = VERDICT_STYLE[sc.verdict] ?? VERDICT_STYLE.neutral;
              return (
                <div
                  key={sc.stepId}
                  className="flex items-center justify-between rounded-md bg-background px-3 py-1.5 text-xs"
                >
                  <span
                    className="truncate font-medium text-foreground"
                    title={sc.searchName}
                  >
                    {sc.searchName}
                  </span>
                  <div className="flex shrink-0 items-center gap-3 pl-3">
                    <span className="font-mono text-muted-foreground">
                      Recall {sc.recallDelta >= 0 ? "+" : ""}
                      {(sc.recallDelta * 100).toFixed(1)}%
                    </span>
                    <Badge className={`text-[10px] ${vs.bg} ${vs.text} border-0`}>
                      {sc.verdict}
                    </Badge>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Phase 4: Parameter Sensitivity results */}
      {items.sensitivities.length > 0 && (
        <div className="rounded-lg border border-border bg-muted/10 p-3">
          <div className="mb-2 text-xs font-semibold text-foreground">
            {STEP_ANALYSIS_PHASE_LABELS.sensitivity}
            <Badge variant="secondary" className="ml-2 text-[10px]">
              {items.sensitivities.length}
            </Badge>
          </div>
          <div className="space-y-1">
            {items.sensitivities.map((ps) => {
              const changed = Math.abs(ps.recommendedValue - ps.currentValue) > 1e-6;
              return (
                <div
                  key={`${ps.stepId}:${ps.paramName}`}
                  className="flex items-center justify-between rounded-md bg-background px-3 py-1.5 text-xs"
                >
                  <span className="truncate font-medium text-foreground">
                    {ps.paramName}
                    <span className="ml-1 text-muted-foreground">on {ps.stepId}</span>
                  </span>
                  <div className="flex shrink-0 items-center gap-2 pl-3 font-mono">
                    <span className="text-muted-foreground">{ps.currentValue}</span>
                    {changed && (
                      <>
                        <ArrowRight className="h-3 w-3 text-primary" />
                        <span className="font-semibold text-primary">
                          {ps.recommendedValue}
                        </span>
                      </>
                    )}
                    {!changed && <Check className="h-3 w-3 text-green-600" />}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Current activity message */}
      {activePhase && (
        <div className="rounded-lg border border-border bg-muted/20 px-4 py-2.5 text-xs text-muted-foreground">
          <Loader2 className="mr-1.5 inline h-3 w-3 animate-spin" />
          {message}
        </div>
      )}
    </div>
  );
}
