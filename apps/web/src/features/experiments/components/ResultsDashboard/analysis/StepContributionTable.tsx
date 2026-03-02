import type { StepContribution } from "@pathfinder/shared";
import { Badge } from "@/lib/components/ui/Badge";
import { GitBranch, CheckCircle, XCircle, Minus } from "lucide-react";

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function VerdictBadge({ verdict }: { verdict: string }) {
  const styles: Record<string, { className: string; icon: typeof CheckCircle }> = {
    essential: {
      className:
        "border-green-300 bg-green-100 text-green-900 dark:border-green-700 dark:bg-green-900 dark:text-green-200",
      icon: CheckCircle,
    },
    helpful: {
      className:
        "border-blue-300 bg-blue-100 text-blue-900 dark:border-blue-700 dark:bg-blue-900 dark:text-blue-200",
      icon: CheckCircle,
    },
    neutral: {
      className:
        "border-gray-300 bg-gray-100 text-gray-700 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-300",
      icon: Minus,
    },
    harmful: {
      className:
        "border-red-300 bg-red-100 text-red-900 dark:border-red-700 dark:bg-red-900 dark:text-red-200",
      icon: XCircle,
    },
  };
  const s = styles[verdict] ?? styles.neutral;
  const Icon = s.icon;
  return (
    <Badge className={`gap-1 text-xs font-semibold capitalize ${s.className}`}>
      <Icon className="h-3 w-3" />
      {verdict}
    </Badge>
  );
}

interface StepContributionTableProps {
  contributions: StepContribution[];
}

export function StepContributionTable({ contributions }: StepContributionTableProps) {
  if (contributions.length === 0) return null;
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">
          Step Contribution (Ablation)
        </h3>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-2 font-medium">Step</th>
              <th className="px-4 py-2 font-medium text-right">Baseline Recall</th>
              <th className="px-4 py-2 font-medium text-right">Without Step</th>
              <th className="px-4 py-2 font-medium text-right">Recall Delta</th>
              <th className="px-4 py-2 font-medium text-right">FPR Delta</th>
              <th className="px-4 py-2 font-medium">Verdict</th>
              <th className="px-4 py-2 font-medium">Why it matters</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {contributions.map((c) => (
              <tr key={c.stepId}>
                <td className="px-4 py-2 font-medium text-foreground">
                  {c.searchName}
                </td>
                <td className="px-4 py-2 text-right font-mono tabular-nums">
                  {pct(c.baselineRecall)}
                </td>
                <td className="px-4 py-2 text-right font-mono tabular-nums">
                  {pct(c.ablatedRecall)}
                </td>
                <td className="px-4 py-2 text-right">
                  <span
                    className={`font-mono tabular-nums font-medium ${
                      c.recallDelta < -0.02
                        ? "text-red-600"
                        : c.recallDelta > 0.02
                          ? "text-green-600"
                          : "text-muted-foreground"
                    }`}
                  >
                    {c.recallDelta >= 0 ? "+" : ""}
                    {pct(c.recallDelta)}
                  </span>
                </td>
                <td className="px-4 py-2 text-right">
                  <span
                    className={`font-mono tabular-nums font-medium ${
                      c.fprDelta < -0.02
                        ? "text-green-600"
                        : c.fprDelta > 0.02
                          ? "text-red-600"
                          : "text-muted-foreground"
                    }`}
                  >
                    {c.fprDelta >= 0 ? "+" : ""}
                    {pct(c.fprDelta)}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <VerdictBadge verdict={c.verdict} />
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground max-w-xs">
                  {c.narrative || "\u2014"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
