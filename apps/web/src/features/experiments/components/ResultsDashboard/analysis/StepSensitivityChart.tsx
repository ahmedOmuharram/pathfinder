import type { ParameterSensitivity } from "@pathfinder/shared";
import { Badge } from "@/lib/components/ui/Badge";
import { SlidersHorizontal } from "lucide-react";

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

interface StepSensitivityChartProps {
  sensitivities: ParameterSensitivity[];
}

export function StepSensitivityChart({ sensitivities }: StepSensitivityChartProps) {
  if (sensitivities.length === 0) return null;
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <SlidersHorizontal className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">Parameter Sensitivity</h3>
      </div>
      <div className="space-y-4">
        {sensitivities.map((s) => (
          <div
            key={`${s.stepId}-${s.paramName}`}
            className="rounded-lg border border-border"
          >
            <div className="flex items-center gap-2 border-b border-border px-4 py-2">
              <span className="text-xs font-medium text-foreground">{s.paramName}</span>
              <span className="text-xs text-muted-foreground">on</span>
              <Badge variant="outline" className="font-mono text-xs">
                {s.stepId}
              </Badge>
              <span className="ml-auto text-xs text-muted-foreground">
                Current:{" "}
                <span className="font-mono font-medium text-foreground">
                  {s.currentValue}
                </span>
              </span>
              {s.recommendedValue !== s.currentValue && (
                <span className="text-xs text-muted-foreground">
                  Recommended:{" "}
                  <span className="font-mono font-medium text-green-600">
                    {s.recommendedValue}
                  </span>
                </span>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-4 py-2 font-medium">Value</th>
                    <th className="px-4 py-2 font-medium text-right">Results</th>
                    <th className="px-4 py-2 font-medium text-right">Recall</th>
                    <th className="px-4 py-2 font-medium text-right">FPR</th>
                    <th className="px-4 py-2 font-medium text-right">F1</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {s.sweepPoints.map((p) => {
                    const isCurrent = Math.abs(p.value - s.currentValue) < 1e-6;
                    const isRecommended = Math.abs(p.value - s.recommendedValue) < 1e-6;
                    return (
                      <tr
                        key={p.value}
                        className={
                          isRecommended && !isCurrent
                            ? "bg-green-50/50 dark:bg-green-950/20"
                            : isCurrent
                              ? "bg-blue-50/50 dark:bg-blue-950/20"
                              : ""
                        }
                      >
                        <td className="px-4 py-2 font-mono tabular-nums font-medium text-foreground">
                          {p.value}
                          {isCurrent && (
                            <span className="ml-1 text-[10px] text-blue-600">
                              (current)
                            </span>
                          )}
                          {isRecommended && !isCurrent && (
                            <span className="ml-1 text-[10px] text-green-600">
                              (recommended)
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">
                          {p.totalResults.toLocaleString()}
                        </td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">
                          {pct(p.recall)}
                        </td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums">
                          {pct(p.fpr)}
                        </td>
                        <td className="px-4 py-2 text-right font-mono tabular-nums font-medium">
                          {p.f1.toFixed(3)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {s.recommendation && (
              <div className="border-t border-border px-4 py-2 text-xs text-muted-foreground">
                {s.recommendation}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
