import type {
  StepAnalysisResult,
  StepEvaluation,
  OperatorComparison,
} from "@pathfinder/shared";
import { Badge } from "@/lib/components/ui/Badge";
import { FlaskConical, Shuffle, AlertTriangle } from "lucide-react";
import { StepContributionTable } from "./StepContributionTable";
import { StepSensitivityChart } from "./StepSensitivityChart";

interface StepDecompositionSectionProps {
  stepAnalysis: StepAnalysisResult;
}

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function DeltaCell({ value }: { value: number }) {
  if (value === 0) return <span className="text-muted-foreground">&mdash;</span>;
  const isPositive = value > 0;
  return (
    <span
      className={`font-mono tabular-nums font-medium ${isPositive ? "text-green-600" : "text-red-600"}`}
    >
      {isPositive ? "+" : ""}
      {value}
    </span>
  );
}

function StepEvaluationTable({ evaluations }: { evaluations: StepEvaluation[] }) {
  if (evaluations.length === 0) return null;

  const worstTpStep = evaluations.reduce<StepEvaluation | null>((worst, e) => {
    if (!worst || e.tpMovement < worst.tpMovement) return e;
    return worst;
  }, null);

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <FlaskConical className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">Per-Step Evaluation</h3>
      </div>
      {worstTpStep && worstTpStep.tpMovement < -2 && (
        <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
          Step &ldquo;{worstTpStep.displayName}&rdquo; removed the most true positives (
          {Math.abs(worstTpStep.tpMovement)} vs baseline).
        </div>
      )}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-2 font-medium">Step</th>
              <th className="px-4 py-2 font-medium text-right">Results</th>
              <th className="px-4 py-2 font-medium text-right">Pos Hits</th>
              <th className="px-4 py-2 font-medium text-right">Recall</th>
              <th className="px-4 py-2 font-medium text-right">FPR</th>
              <th
                className="px-4 py-2 font-medium text-right"
                title="TP change vs baseline"
              >
                TP &Delta;
              </th>
              <th
                className="px-4 py-2 font-medium text-right"
                title="FP change vs baseline"
              >
                FP &Delta;
              </th>
              <th
                className="px-4 py-2 font-medium text-right"
                title="FN change vs baseline"
              >
                FN &Delta;
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {evaluations.map((e) => (
              <tr key={e.stepId}>
                <td className="px-4 py-2">
                  <div className="font-medium text-foreground">{e.displayName}</div>
                  <div className="text-[10px] text-muted-foreground">
                    {e.searchName}
                  </div>
                </td>
                <td className="px-4 py-2 text-right font-mono tabular-nums text-foreground">
                  {e.resultCount.toLocaleString()}
                </td>
                <td className="px-4 py-2 text-right font-mono tabular-nums text-foreground">
                  {e.positiveHits}/{e.positiveTotal}
                </td>
                <td className="px-4 py-2 text-right">
                  <span
                    className={`font-mono tabular-nums font-medium ${
                      e.recall >= 0.8
                        ? "text-green-600"
                        : e.recall >= 0.5
                          ? "text-amber-600"
                          : "text-red-600"
                    }`}
                  >
                    {pct(e.recall)}
                  </span>
                </td>
                <td className="px-4 py-2 text-right">
                  <span
                    className={`font-mono tabular-nums font-medium ${
                      e.falsePositiveRate <= 0.1
                        ? "text-green-600"
                        : e.falsePositiveRate <= 0.3
                          ? "text-amber-600"
                          : "text-red-600"
                    }`}
                  >
                    {pct(e.falsePositiveRate)}
                  </span>
                </td>
                <td className="px-4 py-2 text-right">
                  <DeltaCell value={e.tpMovement} />
                </td>
                <td className="px-4 py-2 text-right">
                  <DeltaCell value={e.fpMovement} />
                </td>
                <td className="px-4 py-2 text-right">
                  <DeltaCell value={e.fnMovement} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function OperatorComparisonTable({
  comparisons,
}: {
  comparisons: OperatorComparison[];
}) {
  if (comparisons.length === 0) return null;
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <Shuffle className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">Operator Comparison</h3>
      </div>
      <div className="space-y-4">
        {comparisons.map((c) => (
          <div key={c.combineNodeId} className="rounded-lg border border-border">
            <div className="flex items-center gap-2 border-b border-border px-4 py-2">
              <span className="text-xs font-medium text-muted-foreground">
                Combine node:
              </span>
              <Badge variant="outline" className="font-mono text-xs">
                {c.combineNodeId}
              </Badge>
              <span className="text-xs text-muted-foreground">Current:</span>
              <Badge variant="secondary" className="text-xs">
                {c.currentOperator}
              </Badge>
              {c.recommendedOperator !== c.currentOperator && (
                <>
                  <span className="text-xs text-muted-foreground">Recommended:</span>
                  <Badge className="text-xs border-green-300 bg-green-100 text-green-900 dark:border-green-700 dark:bg-green-900 dark:text-green-200">
                    {c.recommendedOperator}
                  </Badge>
                </>
              )}
            </div>
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2 font-medium">Operator</th>
                  <th className="px-4 py-2 font-medium text-right">Results</th>
                  <th className="px-4 py-2 font-medium text-right">Pos Hits</th>
                  <th className="px-4 py-2 font-medium text-right">Recall</th>
                  <th className="px-4 py-2 font-medium text-right">Neg Hits</th>
                  <th className="px-4 py-2 font-medium text-right">FPR</th>
                  <th className="px-4 py-2 font-medium text-right">F1</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {c.variants.map((v) => {
                  const isCurrent = v.operator === c.currentOperator;
                  const isBest = v.operator === c.recommendedOperator;
                  return (
                    <tr
                      key={v.operator}
                      className={
                        isBest && !isCurrent
                          ? "bg-green-50/50 dark:bg-green-950/20"
                          : ""
                      }
                    >
                      <td className="px-4 py-2 font-medium text-foreground">
                        {v.operator}
                        {isCurrent && (
                          <span className="ml-1.5 text-[10px] text-muted-foreground">
                            (current)
                          </span>
                        )}
                        {isBest && !isCurrent && (
                          <span className="ml-1.5 text-[10px] text-green-600">
                            (recommended)
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums">
                        {v.totalResults.toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums">
                        {v.positiveHits}
                      </td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums">
                        {pct(v.recall)}
                      </td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums">
                        {v.negativeHits}
                      </td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums">
                        {pct(v.falsePositiveRate)}
                      </td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums font-medium">
                        {v.f1Score.toFixed(3)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {c.recommendation && (
              <div className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
                {c.recommendation}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function StepDecompositionSection({
  stepAnalysis,
}: StepDecompositionSectionProps) {
  const hasEvals = stepAnalysis.stepEvaluations.length > 0;
  const hasOps = stepAnalysis.operatorComparisons.length > 0;
  const hasContributions = stepAnalysis.stepContributions.length > 0;
  const hasSensitivities = stepAnalysis.parameterSensitivities.length > 0;

  if (!hasEvals && !hasOps && !hasContributions && !hasSensitivities) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-border py-8 text-center text-sm text-muted-foreground">
        <AlertTriangle className="h-5 w-5" />
        No step analysis results available.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-2">
        <FlaskConical className="h-5 w-5 text-primary" />
        <h2 className="text-base font-semibold text-foreground">Strategy Analysis</h2>
      </div>

      {hasEvals && <StepEvaluationTable evaluations={stepAnalysis.stepEvaluations} />}
      {hasOps && (
        <OperatorComparisonTable comparisons={stepAnalysis.operatorComparisons} />
      )}
      {hasContributions && (
        <StepContributionTable contributions={stepAnalysis.stepContributions} />
      )}
      {hasSensitivities && (
        <StepSensitivityChart sensitivities={stepAnalysis.parameterSensitivities} />
      )}
    </div>
  );
}
