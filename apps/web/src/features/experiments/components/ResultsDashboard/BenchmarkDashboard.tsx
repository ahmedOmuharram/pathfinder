import { useState, useMemo } from "react";
import type { Experiment, ExperimentMetrics } from "@pathfinder/shared";
import { ArrowLeft, Star, ChevronRight, BarChart3, Layers } from "lucide-react";
import { Badge } from "@/lib/components/ui/Badge";
import { Button } from "@/lib/components/ui/Button";
import { useExperimentStore } from "../../store";
import { ResultsDashboard } from "./index";

interface BenchmarkDashboardProps {
  experiments: Experiment[];
  siteId: string;
}

type MetricKey =
  | "sensitivity"
  | "precision"
  | "f1Score"
  | "mcc"
  | "specificity"
  | "balancedAccuracy"
  | "falsePositiveRate"
  | "totalResults";

const METRIC_COLUMNS: {
  key: MetricKey;
  label: string;
  format: (v: number) => string;
}[] = [
  { key: "sensitivity", label: "Recall", format: pct },
  { key: "precision", label: "Precision", format: pct },
  { key: "f1Score", label: "F1", format: pct },
  { key: "mcc", label: "MCC", format: (v) => v.toFixed(3) },
  { key: "specificity", label: "Specificity", format: pct },
  { key: "balancedAccuracy", label: "Bal. Acc.", format: pct },
  { key: "falsePositiveRate", label: "FPR", format: pct },
  { key: "totalResults", label: "Set Size", format: (v) => v.toLocaleString() },
];

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function getVerdictLevel(metrics: ExperimentMetrics | null): string {
  if (!metrics) return "pending";
  if (metrics.f1Score > 0.8) return "excellent";
  if (metrics.f1Score > 0.6) return "good";
  if (metrics.f1Score > 0.4) return "moderate";
  return "poor";
}

const VERDICT_COLORS: Record<string, string> = {
  excellent: "text-green-600 dark:text-green-400",
  good: "text-blue-600 dark:text-blue-400",
  moderate: "text-amber-600 dark:text-amber-400",
  poor: "text-red-600 dark:text-red-400",
  pending: "text-muted-foreground",
};

const ROW_HOVER = "hover:bg-muted/50 transition cursor-pointer";

function bestInColumn(experiments: Experiment[], key: MetricKey): number | null {
  const values = experiments
    .map((e) => e.metrics?.[key] ?? null)
    .filter((v): v is number => v != null);
  if (values.length === 0) return null;
  if (key === "falsePositiveRate") return Math.min(...values);
  return Math.max(...values);
}

export function BenchmarkDashboard({ experiments, siteId }: BenchmarkDashboardProps) {
  const { setView } = useExperimentStore();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const primary = useMemo(
    () => experiments.find((e) => e.isPrimaryBenchmark) ?? experiments[0],
    [experiments],
  );

  const bests = useMemo(() => {
    const map: Partial<Record<MetricKey, number | null>> = {};
    for (const col of METRIC_COLUMNS) {
      map[col.key] = bestInColumn(experiments, col.key);
    }
    return map;
  }, [experiments]);

  const expandedExperiment = useMemo(
    () => (expandedId ? experiments.find((e) => e.id === expandedId) : null),
    [expandedId, experiments],
  );

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl px-8 py-6 animate-fade-in">
        <header className="mb-6">
          <button
            type="button"
            onClick={() => setView("list")}
            className="mb-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-3 w-3" />
            Experiments
          </button>
          <div className="flex items-center gap-3">
            <Layers className="h-5 w-5 text-primary" />
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              Benchmark Suite
            </h1>
            <Badge className="text-xs">
              {experiments.length} control set{experiments.length !== 1 ? "s" : ""}
            </Badge>
          </div>
          {primary?.config.name && (
            <p className="mt-1 text-sm text-muted-foreground">
              Strategy: {primary.config.name.replace(/\[.*\]/, "").trim()}
            </p>
          )}
        </header>

        {/* Summary table */}
        <div className="mb-8 overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40">
                <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                  Control Set
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                  Verdict
                </th>
                {METRIC_COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    className="px-3 py-2 text-right text-xs font-medium text-muted-foreground"
                  >
                    {col.label}
                  </th>
                ))}
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {experiments.map((exp) => {
                const verdict = getVerdictLevel(exp.metrics);
                const isExpanded = expandedId === exp.id;
                return (
                  <tr
                    key={exp.id}
                    onClick={() => setExpandedId(isExpanded ? null : exp.id)}
                    className={`border-b border-border last:border-b-0 ${ROW_HOVER} ${
                      exp.isPrimaryBenchmark
                        ? "bg-amber-50/50 dark:bg-amber-950/20"
                        : ""
                    }`}
                  >
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        {exp.isPrimaryBenchmark && (
                          <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                        )}
                        <span className="font-medium text-foreground">
                          {exp.controlSetLabel ?? "Unnamed"}
                        </span>
                        {exp.isPrimaryBenchmark && (
                          <Badge className="border-amber-300 bg-amber-100 text-[10px] text-amber-800 dark:border-amber-700 dark:bg-amber-900 dark:text-amber-300">
                            Primary
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`text-xs font-semibold capitalize ${VERDICT_COLORS[verdict]}`}
                      >
                        {verdict}
                      </span>
                    </td>
                    {METRIC_COLUMNS.map((col) => {
                      const val = exp.metrics?.[col.key] ?? null;
                      const isBest = val != null && bests[col.key] === val;
                      return (
                        <td
                          key={col.key}
                          className={`px-3 py-2.5 text-right font-mono text-xs tabular-nums ${
                            isBest ? "font-bold text-primary" : "text-foreground"
                          }`}
                        >
                          {val != null ? col.format(val) : "—"}
                        </td>
                      );
                    })}
                    <td className="px-2 py-2.5">
                      <ChevronRight
                        className={`h-3.5 w-3.5 text-muted-foreground transition ${
                          isExpanded ? "rotate-90" : ""
                        }`}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Expanded detail */}
        {expandedExperiment && (
          <div className="mb-8 rounded-lg border border-primary/20 bg-card p-1">
            <ResultsDashboard experiment={expandedExperiment} siteId={siteId} />
          </div>
        )}

        {/* Primary detail (always shown) */}
        {!expandedExperiment && primary && (
          <div>
            <div className="mb-4 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold text-foreground">
                Primary Benchmark Detail
              </h2>
              <Badge className="border-amber-300 bg-amber-100 text-[10px] text-amber-800 dark:border-amber-700 dark:bg-amber-900 dark:text-amber-300">
                {primary.controlSetLabel ?? "Primary"}
              </Badge>
            </div>
            <ResultsDashboard experiment={primary} siteId={siteId} />
          </div>
        )}
      </div>
    </div>
  );
}
