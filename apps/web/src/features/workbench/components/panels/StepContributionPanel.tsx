"use client";

import { GitBranch } from "lucide-react";
import type {
  StepAnalysisResult,
  StepContribution,
  StepContributionVerdict,
  StepEvaluation,
  OperatorComparison,
} from "@pathfinder/shared";
import { AnalysisPanelContainer } from "../AnalysisPanelContainer";
import { useWorkbenchStore } from "../../store";

// ---------------------------------------------------------------------------
// Verdict badge color mapping
// ---------------------------------------------------------------------------

const verdictColors: Record<StepContributionVerdict, string> = {
  essential: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  helpful: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  neutral: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  harmful: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
};

function VerdictBadge({ verdict }: { verdict: StepContributionVerdict }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${verdictColors[verdict]}`}
    >
      {verdict}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Sub-sections
// ---------------------------------------------------------------------------

function ContributionTable({ contributions }: { contributions: StepContribution[] }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold text-foreground">Step Contributions</h4>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-1 pr-3 font-medium">Step</th>
              <th className="pb-1 pr-3 font-medium">Recall Delta</th>
              <th className="pb-1 pr-3 font-medium">FPR Delta</th>
              <th className="pb-1 font-medium">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {contributions.map((c) => (
              <tr key={c.stepId} className="border-b border-border/50">
                <td className="py-1.5 pr-3">{c.searchName}</td>
                <td className="py-1.5 pr-3">{formatDelta(c.recallDelta)}</td>
                <td className="py-1.5 pr-3">{formatDelta(c.fprDelta)}</td>
                <td className="py-1.5">
                  <VerdictBadge verdict={c.verdict} />
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
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold text-foreground">
        Operator Comparisons
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-1 pr-3 font-medium">Operator</th>
              <th className="pb-1 pr-3 font-medium">Recall</th>
              <th className="pb-1 pr-3 font-medium">FPR</th>
              <th className="pb-1 font-medium">F1</th>
            </tr>
          </thead>
          <tbody>
            {comparisons.flatMap((c) =>
              (c.variants ?? []).map((v) => (
                <tr
                  key={`${c.combineNodeId}-${v.operator}`}
                  className="border-b border-border/50"
                >
                  <td className="py-1.5 pr-3">
                    {v.operator}
                    {v.operator === c.recommendedOperator && (
                      <span className="ml-1 text-[10px] text-green-600 dark:text-green-400">
                        *
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 pr-3">{v.recall.toFixed(2)}</td>
                  <td className="py-1.5 pr-3">{v.falsePositiveRate.toFixed(2)}</td>
                  <td className="py-1.5">{v.f1Score.toFixed(2)}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StepEvaluationTable({ evaluations }: { evaluations: StepEvaluation[] }) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold text-foreground">
        Per-Step Evaluation
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="pb-1 pr-3 font-medium">Step</th>
              <th className="pb-1 pr-3 font-medium">Results</th>
              <th className="pb-1 pr-3 font-medium">Recall</th>
              <th className="pb-1 font-medium">FPR</th>
            </tr>
          </thead>
          <tbody>
            {evaluations.map((e) => (
              <tr key={e.stepId} className="border-b border-border/50">
                <td className="py-1.5 pr-3">{e.displayName}</td>
                <td className="py-1.5 pr-3">{e.resultCount}</td>
                <td className="py-1.5 pr-3">{e.recall.toFixed(2)}</td>
                <td className="py-1.5">{e.falsePositiveRate.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDelta(value: number): string {
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(3)}`;
}

function getAnalysis(
  experiment: { stepAnalysis?: StepAnalysisResult | null } | null,
): StepAnalysisResult | null {
  if (!experiment) return null;
  return experiment.stepAnalysis ?? null;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function StepContributionPanel() {
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);
  const lastExperiment = useWorkbenchStore((s) => s.lastExperiment);
  const lastExperimentSetId = useWorkbenchStore((s) => s.lastExperimentSetId);

  const experiment = lastExperimentSetId === activeSetId ? lastExperiment : null;
  const analysis = getAnalysis(experiment);
  const hasContributions = Boolean(
    analysis && (analysis.stepContributions?.length ?? 0) > 0,
  );

  return (
    <AnalysisPanelContainer
      panelId="step-analysis"
      title="Step Contribution"
      subtitle="Analyze each step's contribution to strategy performance"
      icon={<GitBranch className="h-4 w-4" />}
      disabled={!hasContributions}
      disabledReason="Requires a completed step analysis"
    >
      {analysis && (
        <div className="space-y-5">
          {(analysis.stepContributions?.length ?? 0) > 0 && (
            <ContributionTable contributions={analysis.stepContributions ?? []} />
          )}
          {(analysis.operatorComparisons?.length ?? 0) > 0 && (
            <OperatorComparisonTable comparisons={analysis.operatorComparisons ?? []} />
          )}
          {(analysis.stepEvaluations?.length ?? 0) > 0 && (
            <StepEvaluationTable evaluations={analysis.stepEvaluations ?? []} />
          )}
        </div>
      )}
    </AnalysisPanelContainer>
  );
}
