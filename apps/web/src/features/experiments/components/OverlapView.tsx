import { useState, useEffect, useMemo } from "react";
import type { ExperimentSummary } from "@pathfinder/shared";
import { toUserMessage } from "@/lib/api/errors";
import { useExperimentStore } from "../store";
import { computeOverlap, type OverlapResult } from "../api";
import { ArrowLeft, ArrowUpDown, Loader2 } from "lucide-react";

interface OverlapViewProps {
  experiments: ExperimentSummary[];
}

export function OverlapView({ experiments }: OverlapViewProps) {
  const { setView } = useExperimentStore();
  const [selected, setSelected] = useState<Set<string>>(() => {
    const first2 = experiments.filter((e) => e.status === "completed").slice(0, 2);
    return new Set(first2.map((e) => e.id));
  });
  const [orthologAware, setOrthologAware] = useState(false);
  const [result, setResult] = useState<OverlapResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedIds = useMemo(() => Array.from(selected), [selected]);

  useEffect(() => {
    if (selectedIds.length < 2) {
      queueMicrotask(() => setResult(null));
      return;
    }
    queueMicrotask(() => setLoading(true));
    queueMicrotask(() => setError(null));
    computeOverlap(selectedIds, { orthologAware })
      .then(setResult)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [selectedIds, orthologAware]);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-6 px-8 py-6">
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
            Gene Set Overlap
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Compare true-positive gene lists across experiments.
          </p>
        </header>

        {/* Experiment selector */}
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Select experiments (min 2)
          </div>
          <div className="space-y-1 max-h-40 overflow-y-auto">
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
                  <span className="text-xs text-muted-foreground">({e.siteId})</span>
                </label>
              ))}
          </div>
        </div>

        {/* Ortholog-aware toggle */}
        <div className="rounded-lg border border-border bg-card p-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={orthologAware}
              onChange={(e) => setOrthologAware(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-input"
            />
            <span className="text-sm font-medium text-foreground">
              Ortholog-Aware Comparison
            </span>
          </label>
          <p className="mt-1 ml-5.5 text-xs text-muted-foreground">
            Map genes through OrthoMCL ortholog groups before computing overlap. Enables
            meaningful cross-species comparison.
          </p>
        </div>

        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {error}
          </div>
        )}

        {result && !loading && (
          <>
            <PerExperimentSummary data={result.perExperiment} />
            <PairwiseTable data={result.pairwise} />
            <SharedGenesTable
              data={result.geneMembership}
              totalExperiments={result.experimentIds.length}
            />
          </>
        )}
      </div>
    </div>
  );
}

function PerExperimentSummary({ data }: { data: OverlapResult["perExperiment"] }) {
  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-5 py-2.5 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Per-Experiment Summary
      </div>
      <div className="divide-y divide-slate-50">
        {data.map((d) => (
          <div
            key={d.experimentId}
            className="flex items-center justify-between px-5 py-2"
          >
            <span className="text-sm text-foreground truncate">{d.label}</span>
            <div className="flex gap-4 text-xs">
              <span className="text-muted-foreground">
                Total:{" "}
                <span className="font-mono font-medium text-foreground">
                  {d.totalGenes}
                </span>
              </span>
              <span className="text-muted-foreground">
                Unique:{" "}
                <span className="font-mono font-medium text-foreground">
                  {d.uniqueGenes}
                </span>
              </span>
              <span className="text-muted-foreground">
                Shared:{" "}
                <span className="font-mono font-medium text-foreground">
                  {d.sharedGenes}
                </span>
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PairwiseTable({ data }: { data: OverlapResult["pairwise"] }) {
  if (data.length === 0) return null;

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-5 py-2.5 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Pairwise Overlap
      </div>
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
            <th className="px-4 py-2.5 font-medium">Pair</th>
            <th className="px-4 py-2.5 font-medium text-right">Size A</th>
            <th className="px-4 py-2.5 font-medium text-right">Size B</th>
            <th className="px-4 py-2.5 font-medium text-right">Shared</th>
            <th className="px-4 py-2.5 font-medium text-right">Jaccard</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {data.map((p, i) => (
            <tr key={i}>
              <td className="px-4 py-2 text-foreground">
                <span className="font-medium">{p.labelA}</span>
                <span className="mx-1.5 text-muted-foreground">vs</span>
                <span className="font-medium">{p.labelB}</span>
              </td>
              <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                {p.sizeA}
              </td>
              <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                {p.sizeB}
              </td>
              <td className="px-4 py-2 text-right font-mono tabular-nums text-muted-foreground">
                {p.intersection}
              </td>
              <td className="px-4 py-2 text-right font-mono tabular-nums text-foreground font-semibold">
                {(p.jaccard * 100).toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SharedGenesTable({
  data,
  totalExperiments,
}: {
  data: OverlapResult["geneMembership"];
  totalExperiments: number;
}) {
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(() => {
    const copy = [...data];
    copy.sort((a, b) =>
      sortDir === "desc" ? b.foundIn - a.foundIn : a.foundIn - b.foundIn,
    );
    return copy;
  }, [data, sortDir]);

  if (data.length === 0) return null;

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-5 py-2.5 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Shared Genes ({data.length} total unique)
      </div>
      <div className="max-h-72 overflow-y-auto">
        <table className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-card">
            <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">Gene ID</th>
              <th
                className="px-4 py-2.5 font-medium text-right cursor-pointer select-none"
                onClick={() => setSortDir(sortDir === "desc" ? "asc" : "desc")}
              >
                <span className="inline-flex items-center gap-1">
                  Found In
                  <ArrowUpDown className="h-2.5 w-2.5" />
                </span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {sorted.slice(0, 200).map((g) => (
              <tr key={g.geneId}>
                <td className="px-4 py-1.5 font-mono text-foreground">{g.geneId}</td>
                <td className="px-4 py-1.5 text-right">
                  <span className="font-mono tabular-nums font-medium text-foreground">
                    {g.foundIn}
                  </span>
                  <span className="text-muted-foreground"> / {totalExperiments}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {sorted.length > 200 && (
          <div className="px-4 py-2 text-xs text-muted-foreground">
            Showing 200 of {sorted.length} genes
          </div>
        )}
      </div>
    </div>
  );
}
