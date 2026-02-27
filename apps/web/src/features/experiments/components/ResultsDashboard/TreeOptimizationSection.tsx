import type { TreeOptimizationDiff, ExperimentMetrics } from "@pathfinder/shared";
import { ArrowRight, Check, Minus, Plus, Sparkles } from "lucide-react";
import { Badge } from "@/lib/components/ui/Badge";

interface TreeOptimizationSectionProps {
  diff: TreeOptimizationDiff;
}

function MetricsComparison({
  label,
  before,
  after,
}: {
  label: string;
  before: number;
  after: number;
}) {
  const improved = after > before;
  const change = after - before;
  const pct = before > 0 ? ((change / before) * 100).toFixed(1) : "N/A";

  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-muted-foreground">
          {before.toFixed(4)}
        </span>
        <ArrowRight className="h-3 w-3 text-muted-foreground" />
        <span
          className={`font-mono text-xs font-semibold ${
            improved
              ? "text-green-600 dark:text-green-400"
              : change < 0
                ? "text-red-600 dark:text-red-400"
                : "text-foreground"
          }`}
        >
          {after.toFixed(4)}
        </span>
        {change !== 0 && (
          <Badge
            variant="outline"
            className={`text-[10px] ${
              improved
                ? "border-green-300 text-green-700 dark:border-green-700 dark:text-green-400"
                : "border-red-300 text-red-700 dark:border-red-700 dark:text-red-400"
            }`}
          >
            {improved ? "+" : ""}
            {typeof pct === "string" && pct !== "N/A" ? `${pct}%` : change.toFixed(4)}
          </Badge>
        )}
      </div>
    </div>
  );
}

export function TreeOptimizationSection({ diff }: TreeOptimizationSectionProps) {
  const { baselineMetrics, bestMetrics, mutations, baselineScore, bestScore } = diff;

  const improved = bestScore > baselineScore;

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">
          Tree Optimization Results
        </h3>
        <Badge
          variant="outline"
          className={
            improved
              ? "border-green-300 text-green-700 dark:border-green-700 dark:text-green-400"
              : "border-muted text-muted-foreground"
          }
        >
          {improved
            ? `+${((bestScore - baselineScore) * 100).toFixed(1)}% improvement`
            : "No improvement found"}
        </Badge>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <div className="mb-3 text-xs text-muted-foreground">
          {diff.totalTrials} trial{diff.totalTrials !== 1 ? "s" : ""} run,{" "}
          {diff.successfulTrials} successful
        </div>

        {/* Score comparison */}
        <div className="rounded-md border border-border bg-background p-3">
          <MetricsComparison
            label="Objective Score"
            before={baselineScore}
            after={bestScore}
          />
          {baselineMetrics && bestMetrics && (
            <>
              <MetricsComparison
                label="Sensitivity"
                before={baselineMetrics.sensitivity}
                after={bestMetrics.sensitivity}
              />
              <MetricsComparison
                label="Specificity"
                before={baselineMetrics.specificity}
                after={bestMetrics.specificity}
              />
              <MetricsComparison
                label="F1 Score"
                before={baselineMetrics.f1Score}
                after={bestMetrics.f1Score}
              />
              <MetricsComparison
                label="Balanced Accuracy"
                before={baselineMetrics.balancedAccuracy}
                after={bestMetrics.balancedAccuracy}
              />
              <MetricsComparison
                label="MCC"
                before={baselineMetrics.mcc}
                after={bestMetrics.mcc}
              />
            </>
          )}
        </div>

        {/* Mutations */}
        {mutations.length > 0 && (
          <div className="mt-4">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Changes Made ({mutations.length})
            </h4>
            <div className="space-y-1.5">
              {mutations.map((m, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 rounded border border-border bg-background px-3 py-2 text-xs"
                >
                  {m.kind === "param" && (
                    <>
                      <Badge variant="outline" className="text-[10px]">
                        Param
                      </Badge>
                      <span className="font-mono text-muted-foreground">
                        {m.fieldName}
                      </span>
                      <span className="text-muted-foreground line-through">
                        {m.originalValue}
                      </span>
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      <span className="font-semibold text-primary">{m.newValue}</span>
                      <span className="ml-auto text-[10px] text-muted-foreground">
                        on {m.nodeId}
                      </span>
                    </>
                  )}
                  {m.kind === "operator" && (
                    <>
                      <Badge
                        variant="outline"
                        className="border-amber-300 text-[10px] text-amber-700 dark:border-amber-700 dark:text-amber-400"
                      >
                        Operator
                      </Badge>
                      <span className="text-muted-foreground line-through">
                        {m.originalValue}
                      </span>
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      <span className="font-semibold text-amber-700 dark:text-amber-400">
                        {m.newValue}
                      </span>
                      <span className="ml-auto text-[10px] text-muted-foreground">
                        at {m.nodeId}
                      </span>
                    </>
                  )}
                  {m.kind === "ortholog_insert" && (
                    <>
                      <Badge
                        variant="outline"
                        className="border-purple-300 text-[10px] text-purple-700 dark:border-purple-700 dark:text-purple-400"
                      >
                        Ortholog
                      </Badge>
                      <Plus className="h-3 w-3 text-purple-600" />
                      <span className="font-semibold text-purple-700 dark:text-purple-400">
                        {m.newValue}
                      </span>
                      <span className="ml-auto text-[10px] text-muted-foreground">
                        after {m.nodeId}
                      </span>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {mutations.length === 0 && improved && (
          <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
            <Check className="h-3 w-3 text-green-500" />
            Original tree was already near-optimal for the given controls.
          </div>
        )}
      </div>
    </section>
  );
}
