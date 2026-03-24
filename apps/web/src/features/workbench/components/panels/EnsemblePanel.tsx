"use client";

import { useState, useCallback } from "react";
import { Layers, Loader2 } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { requestJson } from "@/lib/api/http";
import { AnalysisPanelContainer } from "../AnalysisPanelContainer";
import { GeneChipInput } from "../GeneChipInput";
import { useWorkbenchStore } from "@/state/useWorkbenchStore";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EnsembleScore {
  geneId: string;
  frequency: number;
  count: number;
  total: number;
  inPositives: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EnsemblePanel() {
  const geneSets = useWorkbenchStore((s) => s.geneSets);
  const selectedSetIds = useWorkbenchStore((s) => s.selectedSetIds);
  const toggleSetSelection = useWorkbenchStore((s) => s.toggleSetSelection);

  const [positiveControls, setPositiveControls] = useState<string[]>([]);
  const [results, setResults] = useState<EnsembleScore[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasEnoughSets = geneSets.length >= 2;
  const canCompute = selectedSetIds.length >= 2;

  const handleCompute = useCallback(async () => {
    if (!canCompute) return;

    const selectedSets = geneSets.filter((gs) => selectedSetIds.includes(gs.id));
    const sites = new Set(selectedSets.map((gs) => gs.siteId));
    if (sites.size > 1) {
      setError(
        "Selected gene sets are from different sites. Results may be meaningless.",
      );
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const data = await requestJson<EnsembleScore[]>("/api/v1/gene-sets/ensemble", {
        method: "POST",
        body: {
          geneSetIds: selectedSetIds,
          positiveControls: positiveControls.length > 0 ? positiveControls : undefined,
        },
      });
      setResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [canCompute, selectedSetIds, positiveControls, geneSets]);

  return (
    <AnalysisPanelContainer
      panelId="ensemble"
      title="Ensemble Scoring"
      subtitle="Score genes by frequency across multiple gene sets"
      icon={<Layers className="h-4 w-4" />}
      disabled={!hasEnoughSets}
      disabledReason="Requires at least 2 gene sets"
    >
      <div className="space-y-4">
        {/* Gene set selector */}
        <div>
          <p className="mb-1 text-xs font-medium text-muted-foreground">
            Select gene sets (2+)
          </p>
          <div className="flex flex-wrap gap-1.5">
            {geneSets.map((gs) => {
              const selected = selectedSetIds.includes(gs.id);
              return (
                <button
                  key={gs.id}
                  type="button"
                  className={`rounded-full border px-2.5 py-0.5 text-[10px] font-medium transition-colors ${
                    selected
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-input text-muted-foreground hover:border-foreground/30"
                  }`}
                  onClick={() => toggleSetSelection(gs.id)}
                >
                  {gs.name}
                </button>
              );
            })}
          </div>
        </div>

        {/* Optional positive controls */}
        <GeneChipInput
          siteId={geneSets[0]?.siteId ?? ""}
          value={positiveControls}
          onChange={setPositiveControls}
          label="Positive Controls (optional)"
        />

        {/* Compute button */}
        <Button
          size="sm"
          onClick={() => {
            void handleCompute();
          }}
          disabled={!canCompute || loading}
        >
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Layers className="h-3.5 w-3.5" />
          )}
          {loading ? "Computing..." : "Compute"}
        </Button>

        {error != null && error !== "" && (
          <p className="text-xs text-destructive">{error}</p>
        )}

        {/* Results table */}
        {results != null && results.length > 0 && (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b bg-muted/50 text-left text-muted-foreground">
                  <th className="px-3 py-2">Gene ID</th>
                  <th className="px-3 py-2 text-right">Frequency</th>
                  <th className="px-3 py-2 text-right">Count</th>
                  <th className="px-3 py-2 text-center">In Positives</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.geneId} className="border-b last:border-0">
                    <td className="px-3 py-1.5 font-mono">{r.geneId}</td>
                    <td className="px-3 py-1.5 text-right">
                      {(r.frequency * 100).toFixed(1)}%
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      {r.count}/{r.total}
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      {r.inPositives ? (
                        <span className="text-green-600 dark:text-green-400">Yes</span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {results?.length === 0 && (
          <p className="text-xs text-muted-foreground">
            No genes found across the selected sets.
          </p>
        )}
      </div>
    </AnalysisPanelContainer>
  );
}
