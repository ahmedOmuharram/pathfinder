import { useState, useEffect, useMemo } from "react";
import type { ExperimentSummary } from "@pathfinder/shared";
import { useExperimentStore } from "../store";
import { compareEnrichment, type EnrichmentCompareResult } from "../api";
import { ArrowLeft, Loader2 } from "lucide-react";

interface EnrichmentCompareViewProps {
  experiments: ExperimentSummary[];
}

const ANALYSIS_LABELS: Record<string, string> = {
  go_function: "GO: Molecular Function",
  go_component: "GO: Cellular Component",
  go_process: "GO: Biological Process",
  pathway: "Metabolic Pathway",
  word: "Word Enrichment",
};

export function EnrichmentCompareView({ experiments }: EnrichmentCompareViewProps) {
  const { setView } = useExperimentStore();
  const [selected, setSelected] = useState<Set<string>>(() => {
    const first = experiments.filter((e) => e.status === "completed").slice(0, 3);
    return new Set(first.map((e) => e.id));
  });
  const [analysisType, setAnalysisType] = useState<string>("");
  const [result, setResult] = useState<EnrichmentCompareResult | null>(null);
  const [loading, setLoading] = useState(false);

  const selectedIds = useMemo(() => Array.from(selected), [selected]);

  useEffect(() => {
    if (selectedIds.length < 2) {
      queueMicrotask(() => setResult(null));
      return;
    }
    queueMicrotask(() => setLoading(true));
    compareEnrichment(selectedIds, analysisType || undefined)
      .then(setResult)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedIds, analysisType]);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-6 px-8 py-6">
        <header>
          <button
            type="button"
            onClick={() => setView("list")}
            className="mb-3 inline-flex items-center gap-1.5 text-xs text-muted-foreground transition hover:text-muted-foreground"
          >
            <ArrowLeft className="h-3 w-3" />
            Back
          </button>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            Enrichment Comparison
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Compare enrichment significance (-log10 p-value) across experiments.
          </p>
        </header>

        <div className="flex gap-4">
          {/* Experiment selector */}
          <div className="w-64 shrink-0 rounded-lg border border-border bg-card p-4">
            <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Experiments (min 2)
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {experiments
                .filter((e) => e.status === "completed")
                .map((e) => (
                  <label key={e.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selected.has(e.id)}
                      onChange={(ev) => {
                        const next = new Set(selected);
                        if (ev.target.checked) next.add(e.id);
                        else next.delete(e.id);
                        setSelected(next);
                      }}
                      className="h-3.5 w-3.5 rounded border-input"
                    />
                    <span className="text-sm text-foreground truncate">{e.name}</span>
                  </label>
                ))}
            </div>
            <div className="mt-3">
              <div className="mb-1 text-xs text-muted-foreground">Filter by type</div>
              <select
                value={analysisType}
                onChange={(e) => setAnalysisType(e.target.value)}
                className="w-full rounded border border-border px-2 py-1 text-xs text-muted-foreground outline-none"
              >
                <option value="">All types</option>
                {Object.entries(ANALYSIS_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Heatmap */}
          <div className="min-w-0 flex-1">
            {loading && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            )}
            {result && !loading && <Heatmap result={result} />}
          </div>
        </div>
      </div>
    </div>
  );
}

function Heatmap({ result }: { result: EnrichmentCompareResult }) {
  const expIds = result.experimentIds;
  const maxVal = useMemo(
    () => Math.max(...result.rows.map((r) => r.maxScore), 1),
    [result.rows],
  );

  if (result.rows.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card px-5 py-8 text-center text-xs text-muted-foreground">
        No enrichment terms found across selected experiments.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card overflow-auto max-h-[600px]">
      <table className="text-xs">
        <thead className="sticky top-0 bg-card z-10">
          <tr className="border-b border-border">
            <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground sticky left-0 bg-card">
              Term
            </th>
            <th className="px-2 py-2 text-center text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Type
            </th>
            {expIds.map((eid) => (
              <th
                key={eid}
                className="px-2 py-2 text-center text-xs font-medium uppercase tracking-wider text-muted-foreground max-w-[80px] truncate"
                title={result.experimentLabels[eid]}
              >
                {(result.experimentLabels[eid] || eid).slice(0, 12)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row) => (
            <tr key={row.termKey} className="border-b border-border/50">
              <td
                className="px-3 py-1.5 text-foreground max-w-[200px] truncate sticky left-0 bg-card"
                title={row.termName}
              >
                {row.termName}
              </td>
              <td className="px-2 py-1.5 text-center text-xs text-muted-foreground">
                {ANALYSIS_LABELS[row.analysisType]?.split(":")[0] || row.analysisType}
              </td>
              {expIds.map((eid) => {
                const val = row.scores[eid];
                const intensity = val != null ? Math.min(val / maxVal, 1) : 0;
                const bg =
                  val != null
                    ? `rgba(30, 41, 59, ${intensity * 0.8 + 0.05})`
                    : "#f8fafc";
                const color = val != null && intensity > 0.5 ? "#f8fafc" : "#334155";
                return (
                  <td
                    key={eid}
                    className="px-2 py-1.5 text-center font-mono tabular-nums text-xs"
                    style={{ backgroundColor: bg, color }}
                    title={val != null ? `-log10(p) = ${val}` : "N/A"}
                  >
                    {val != null ? val.toFixed(1) : "\u2014"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {result.totalTerms > result.rows.length && (
        <div className="px-3 py-2 text-xs text-muted-foreground border-t border-border">
          Showing {result.rows.length} of {result.totalTerms} terms
        </div>
      )}
    </div>
  );
}
