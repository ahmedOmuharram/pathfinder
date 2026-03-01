import type { BootstrapResult, ConfidenceInterval } from "@pathfinder/shared";
import { Shield } from "lucide-react";
import { Badge } from "@/lib/components/ui/Badge";
import { Section } from "./Section";
import { pct, fmtNum } from "./utils";

interface RobustnessSectionProps {
  robustness: BootstrapResult;
}

const METRIC_DISPLAY: Record<string, string> = {
  sensitivity: "Sensitivity",
  specificity: "Specificity",
  precision: "Precision",
  f1_score: "F1 Score",
  precision_at_10: "P@10",
  precision_at_25: "P@25",
  precision_at_50: "P@50",
  precision_at_100: "P@100",
  recall_at_10: "R@10",
  recall_at_25: "R@25",
  recall_at_50: "R@50",
  recall_at_100: "R@100",
  enrichment_at_10: "E@10",
  enrichment_at_25: "E@25",
  enrichment_at_50: "E@50",
  enrichment_at_100: "E@100",
};

function stabilityLabel(score: number): { text: string; className: string } {
  if (score > 0.9)
    return { text: "Very stable", className: "text-green-600 dark:text-green-400" };
  if (score > 0.7)
    return { text: "Stable", className: "text-blue-600 dark:text-blue-400" };
  if (score > 0.5)
    return { text: "Moderate", className: "text-amber-600 dark:text-amber-400" };
  return { text: "Unstable", className: "text-red-600 dark:text-red-400" };
}

function CIRow({
  label,
  ci,
  isEnrichment,
}: {
  label: string;
  ci: ConfidenceInterval;
  isEnrichment?: boolean;
}) {
  const widthIsNarrow = ci.upper - ci.lower < 0.15;
  return (
    <tr className="border-b border-border last:border-0">
      <td className="px-4 py-2 text-sm text-foreground">{label}</td>
      <td className="px-4 py-2 text-right font-mono text-sm tabular-nums">
        {isEnrichment ? `${fmtNum(ci.mean)}x` : pct(ci.mean)}
      </td>
      <td className="px-4 py-2 text-right font-mono text-xs tabular-nums text-muted-foreground">
        [{isEnrichment ? fmtNum(ci.lower) : pct(ci.lower)},{" "}
        {isEnrichment ? fmtNum(ci.upper) : pct(ci.upper)}]
      </td>
      <td className="px-4 py-2 text-right text-xs">
        <Badge
          variant="secondary"
          className={`text-[10px] ${widthIsNarrow ? "text-green-700 dark:text-green-400" : "text-amber-700 dark:text-amber-400"}`}
        >
          {widthIsNarrow ? "Tight" : "Wide"}
        </Badge>
      </td>
    </tr>
  );
}

export function RobustnessSection({ robustness }: RobustnessSectionProps) {
  const allCis = { ...robustness.metricCis, ...(robustness.rankMetricCis ?? {}) };
  const ciEntries = Object.entries(allCis).filter(([k]) => k in METRIC_DISPLAY);
  const hasRankCis = Object.keys(robustness.rankMetricCis ?? {}).length > 0;
  const stability = stabilityLabel(robustness.topKStability);

  return (
    <Section title="Robustness & Uncertainty">
      <div className="space-y-4">
        {/* Stability badge — only shown when rank metrics are present */}
        {hasRankCis && (
          <div className="flex items-center gap-3 rounded-lg border border-border bg-card px-5 py-3">
            <Shield className="h-5 w-5 text-muted-foreground" />
            <div>
              <span className="text-sm font-medium text-foreground">
                Top-50 Stability:
              </span>
              <span className={`ml-2 text-sm font-semibold ${stability.className}`}>
                {fmtNum(robustness.topKStability)} — {stability.text}
              </span>
            </div>
            <span className="ml-auto text-xs text-muted-foreground">
              {robustness.nIterations} bootstrap iterations
            </span>
          </div>
        )}

        {/* CI table */}
        {ciEntries.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                    Metric
                  </th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                    Mean
                  </th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                    95% CI
                  </th>
                  <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                    Width
                  </th>
                </tr>
              </thead>
              <tbody>
                {ciEntries.map(([key, ci]) => (
                  <CIRow
                    key={key}
                    label={METRIC_DISPLAY[key] ?? key}
                    ci={ci}
                    isEnrichment={key.startsWith("enrichment")}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Negative set sensitivity */}
        {(robustness.negativeSetSensitivity ?? []).length > 0 && (
          <div>
            <h4 className="mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Negative Set Sensitivity
            </h4>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                      Negative Set
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                      Size
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                      P@50
                    </th>
                    <th className="px-4 py-2 text-right font-medium text-muted-foreground">
                      E@50
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {robustness.negativeSetSensitivity.map((v) => (
                    <tr key={v.label} className="border-b border-border last:border-0">
                      <td className="px-4 py-2 font-medium">{v.label}</td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums">
                        {v.negativeCount}
                      </td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums">
                        {pct(v.rankMetrics.precisionAtK["50"] ?? 0)}
                      </td>
                      <td className="px-4 py-2 text-right font-mono tabular-nums">
                        {fmtNum(v.rankMetrics.enrichmentAtK["50"] ?? 0)}x
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Section>
  );
}
