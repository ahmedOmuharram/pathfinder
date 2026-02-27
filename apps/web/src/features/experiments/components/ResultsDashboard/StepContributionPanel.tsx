import { useCallback, useEffect, useState } from "react";
import type { PlanStepNode } from "@pathfinder/shared";
import { requestJson } from "@/lib/api/http";
import { Button } from "@/lib/components/ui/Button";
import { Loader2, AlertCircle, BarChart3 } from "lucide-react";

interface StepContribution {
  stepName: string;
  stepSearchName: string;
  totalResults: number;
  positiveControlHits: number;
  negativeControlHits: number;
  positiveRecall: number;
  negativeRecall: number;
}

interface StepContributionPanelProps {
  experimentId: string;
  stepTree: PlanStepNode | null | undefined;
}

/**
 * Recursively flatten a PlanStepNode tree into a list of leaf (search) steps.
 */
function flattenLeafSteps(node: PlanStepNode): PlanStepNode[] {
  const results: PlanStepNode[] = [];
  if (node.primaryInput) {
    results.push(...flattenLeafSteps(node.primaryInput));
  }
  if (node.secondaryInput) {
    results.push(...flattenLeafSteps(node.secondaryInput));
  }
  if (!node.primaryInput && !node.secondaryInput) {
    results.push(node);
  }
  return results;
}

export function StepContributionPanel({
  experimentId,
  stepTree,
}: StepContributionPanelProps) {
  const [contributions, setContributions] = useState<StepContribution[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const leafSteps = stepTree ? flattenLeafSteps(stepTree) : [];

  const fetchContributions = useCallback(async () => {
    if (!stepTree || leafSteps.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const data = await requestJson<{ contributions: StepContribution[] }>(
        `/api/v1/experiments/${experimentId}/step-contributions`,
        { method: "POST", body: { stepTree } },
      );
      setContributions(data.contributions);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [experimentId, stepTree, leafSteps.length]);

  if (!stepTree) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 px-5 py-8 text-center text-sm text-muted-foreground">
        <AlertCircle className="mx-auto mb-2 h-5 w-5" />
        Step contribution analysis is only available for multi-step experiments.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Step Contribution Analysis
          </h3>
          <p className="text-xs text-muted-foreground">
            Evaluate how each search step contributes to the final result and control
            gene capture.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void fetchContributions()}
          disabled={loading}
          loading={loading}
        >
          <BarChart3 className="h-3 w-3" />
          Analyze
        </Button>
      </div>

      {/* Leaf steps overview */}
      <div className="rounded-lg border border-border">
        <div className="border-b border-border bg-muted/30 px-3 py-2">
          <span className="text-xs font-medium text-muted-foreground">
            Search Steps in Strategy ({leafSteps.length})
          </span>
        </div>
        <div className="divide-y divide-border">
          {leafSteps.map((step, i) => (
            <div
              key={step.id ?? i}
              className="flex items-center justify-between px-3 py-2"
            >
              <div>
                <span className="text-sm font-medium text-foreground">
                  {step.displayName || step.searchName}
                </span>
                {step.displayName && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    {step.searchName}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      {/* Results */}
      {contributions && (
        <div className="rounded-lg border border-border">
          <div className="border-b border-border bg-muted/30 px-3 py-2">
            <span className="text-xs font-medium text-muted-foreground">
              Contribution Results
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-muted/20 text-left text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Step</th>
                  <th className="px-3 py-2 font-medium text-right">Results</th>
                  <th className="px-3 py-2 font-medium text-right">+Control Hits</th>
                  <th className="px-3 py-2 font-medium text-right">-Control Hits</th>
                  <th className="px-3 py-2 font-medium text-right">+Recall</th>
                  <th className="px-3 py-2 font-medium text-right">-Recall</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {contributions.map((c, i) => (
                  <tr key={i} className="hover:bg-muted/10">
                    <td className="px-3 py-2 font-medium text-foreground">
                      {c.stepName}
                      <span className="ml-1 text-muted-foreground">
                        ({c.stepSearchName})
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {c.totalResults.toLocaleString()}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-green-600 dark:text-green-400">
                      {c.positiveControlHits}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-red-600 dark:text-red-400">
                      {c.negativeControlHits}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {(c.positiveRecall * 100).toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {(c.negativeRecall * 100).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
