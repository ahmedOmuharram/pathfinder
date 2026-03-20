"use client";

import { useState, useCallback, useEffect } from "react";
import { BarChart3, Play, Loader2, Plus, Trash2 } from "lucide-react";
import type { Experiment, ControlSet } from "@pathfinder/shared";
import { Button } from "@/lib/components/ui/Button";
import { Input } from "@/lib/components/ui/Input";
import {
  listControlSets,
  createBenchmarkStream,
  type BenchmarkControlSetInput,
} from "@/features/workbench/api";
import { CONTROLS_SEARCH_NAME, CONTROLS_PARAM_NAME } from "../../constants";
import { AnalysisPanelContainer } from "../AnalysisPanelContainer";
import { GeneChipInput } from "../GeneChipInput";
import { useWorkbenchStore } from "../../store";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface InlineControlSet {
  id: string;
  label: string;
  positiveControls: string[];
  negativeControls: string[];
  isPrimary: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatMetric(value: number): string {
  return value.toFixed(3);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BenchmarkPanel() {
  const geneSets = useWorkbenchStore((s) => s.geneSets);
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);
  const activeSet = geneSets.find((gs) => gs.id === activeSetId);

  const hasSearchContext = Boolean(
    activeSet != null &&
    (activeSet.geneIds.length > 0 ||
      (activeSet.searchName != null &&
        activeSet.searchName !== "" &&
        activeSet.parameters != null)),
  );

  // Saved control sets
  const [savedSets, setSavedSets] = useState<ControlSet[]>([]);
  const [selectedSavedIds, setSelectedSavedIds] = useState<Set<string>>(new Set());

  // Inline (manually entered) control sets
  const [inlineSets, setInlineSets] = useState<InlineControlSet[]>([]);

  // Streaming state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [controlSetError, setControlSetError] = useState<string | null>(null);
  const [results, setResults] = useState<Experiment[]>([]);

  // Load saved control sets
  useEffect(() => {
    if (activeSet?.siteId == null || activeSet.siteId === "") return;
    let cancelled = false;
    listControlSets(activeSet.siteId)
      .then((sets) => {
        if (!cancelled) setSavedSets(sets);
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("Failed to load control sets:", err);
          setControlSetError("Failed to load saved control sets");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeSet?.siteId]);

  const toggleSavedSet = useCallback((id: string) => {
    setSelectedSavedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const addInlineSet = useCallback(() => {
    setInlineSets((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        label: "",
        positiveControls: [],
        negativeControls: [],
        isPrimary: false,
      },
    ]);
  }, []);

  const removeInlineSet = useCallback((id: string) => {
    setInlineSets((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const updateInlineSet = useCallback(
    (id: string, patch: Partial<InlineControlSet>) => {
      setInlineSets((prev) =>
        prev.map((s) => {
          if (s.id === id) return { ...s, ...patch };
          if (patch.isPrimary === true) return { ...s, isPrimary: false };
          return s;
        }),
      );
    },
    [],
  );

  const handleRun = useCallback(async () => {
    if (!activeSet) return;

    // Build control set inputs from saved selections + inline
    const controlSets: BenchmarkControlSetInput[] = [];

    // Check if any inline set is explicitly marked as primary
    const hasInlinePrimary = inlineSets.some(
      (s) => s.isPrimary && s.positiveControls.length > 0,
    );

    for (const id of selectedSavedIds) {
      const saved = savedSets.find((s) => s.id === id);
      if (!saved) continue;
      controlSets.push({
        label: saved.name,
        positiveControls: saved.positiveIds,
        negativeControls: saved.negativeIds,
        controlSetId: saved.id,
        isPrimary: !hasInlinePrimary && controlSets.length === 0,
      });
    }

    for (const inline of inlineSets) {
      if (inline.positiveControls.length === 0) continue;
      controlSets.push({
        label: inline.label || "Inline Controls",
        positiveControls: inline.positiveControls,
        negativeControls: inline.negativeControls,
        isPrimary: inline.isPrimary,
      });
    }

    // Enforce at most one primary — if multiple, keep only the first
    let foundPrimary = false;
    for (const cs of controlSets) {
      if (cs.isPrimary) {
        if (foundPrimary) cs.isPrimary = false;
        else foundPrimary = true;
      }
    }
    // If none is primary, default the first
    const firstSet = controlSets[0];
    if (!foundPrimary && firstSet != null) {
      firstSet.isPrimary = true;
    }

    if (controlSets.length === 0) {
      setError("Select or add at least one control set with positive controls.");
      return;
    }

    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const benchConfig: Parameters<typeof createBenchmarkStream>[0] = {
        siteId: activeSet.siteId,
        recordType: activeSet.recordType ?? "gene",
        searchName: activeSet.searchName ?? "",
        parameters: activeSet.parameters ?? {},
        positiveControls: [],
        negativeControls: [],
        controlsSearchName: CONTROLS_SEARCH_NAME,
        controlsParamName: CONTROLS_PARAM_NAME,
        controlsValueFormat: "newline",
        enableCrossValidation: false,
        kFolds: 5,
        enrichmentTypes: [],
        name: `Benchmark: ${activeSet.name}`,
      };
      if (activeSet.geneIds.length > 0) benchConfig.targetGeneIds = activeSet.geneIds;
      await createBenchmarkStream(benchConfig, controlSets, {
        onComplete: (experiments) => {
          setResults(experiments);
          setLoading(false);
        },
        onError: (errMsg) => {
          setError(errMsg);
          setLoading(false);
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    }
  }, [activeSet, selectedSavedIds, savedSets, inlineSets]);

  return (
    <AnalysisPanelContainer
      panelId="benchmark"
      title="Benchmark"
      subtitle="Compare strategy performance across multiple control sets"
      icon={<BarChart3 className="h-4 w-4" />}
      disabled={!hasSearchContext}
      disabledReason="Requires a strategy-backed gene set with search parameters"
    >
      <div className="space-y-4">
        {/* Saved control sets */}
        {savedSets.length > 0 && (
          <div>
            <p className="mb-1.5 text-xs font-medium text-muted-foreground">
              Saved Control Sets
            </p>
            <div className="space-y-1">
              {savedSets.map((cs) => (
                <label key={cs.id} className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={selectedSavedIds.has(cs.id)}
                    onChange={() => toggleSavedSet(cs.id)}
                    aria-label={cs.name}
                    className="rounded border-input"
                  />
                  {cs.name}
                  <span className="text-muted-foreground">
                    ({cs.positiveIds.length}+ / {cs.negativeIds.length}−)
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Inline control sets */}
        {inlineSets.map((inline) => (
          <div key={inline.id} className="rounded-md border p-3 space-y-2">
            <div className="flex items-center justify-between">
              <Input
                type="text"
                value={inline.label}
                onChange={(e) => updateInlineSet(inline.id, { label: e.target.value })}
                placeholder="Control set label"
                className="h-auto bg-background px-2 py-1 text-xs"
              />
              <button
                type="button"
                onClick={() => removeInlineSet(inline.id)}
                className="ml-2 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <GeneChipInput
                siteId={activeSet?.siteId ?? ""}
                value={inline.positiveControls}
                onChange={(ids) =>
                  updateInlineSet(inline.id, { positiveControls: ids })
                }
                label="Positive Controls"
                tint="positive"
              />
              <GeneChipInput
                siteId={activeSet?.siteId ?? ""}
                value={inline.negativeControls}
                onChange={(ids) =>
                  updateInlineSet(inline.id, { negativeControls: ids })
                }
                label="Negative Controls"
                tint="negative"
              />
            </div>
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={inline.isPrimary}
                onChange={(e) =>
                  updateInlineSet(inline.id, { isPrimary: e.target.checked })
                }
                className="rounded border-input"
              />
              Primary
            </label>
          </div>
        ))}

        {/* Add inline set button */}
        <button
          type="button"
          onClick={addInlineSet}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <Plus className="h-3.5 w-3.5" /> Add inline control set
        </button>

        {/* Run */}
        <Button
          size="sm"
          onClick={() => {
            void handleRun();
          }}
          disabled={loading}
        >
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Play className="h-3.5 w-3.5" />
          )}
          {loading ? "Running..." : "Run Benchmark"}
        </Button>

        {controlSetError != null && controlSetError !== "" && (
          <p className="text-xs text-destructive">{controlSetError}</p>
        )}
        {error != null && error !== "" && (
          <p className="text-xs text-destructive">{error}</p>
        )}

        {/* Results comparison table */}
        {results.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-3 font-medium">Control Set</th>
                  <th className="py-2 pr-3 font-medium">Sensitivity</th>
                  <th className="py-2 pr-3 font-medium">Specificity</th>
                  <th className="py-2 pr-3 font-medium">F1</th>
                  <th className="py-2 pr-3 font-medium">Precision</th>
                  <th className="py-2 font-medium">MCC</th>
                </tr>
              </thead>
              <tbody>
                {results.map((exp) => (
                  <tr
                    key={exp.id}
                    className={
                      exp.isPrimaryBenchmark ? "bg-primary/10 font-medium" : ""
                    }
                  >
                    <td className="py-1.5 pr-3">{exp.controlSetLabel ?? "—"}</td>
                    <td className="py-1.5 pr-3">
                      {exp.metrics ? formatMetric(exp.metrics.sensitivity) : "—"}
                    </td>
                    <td className="py-1.5 pr-3">
                      {exp.metrics ? formatMetric(exp.metrics.specificity) : "—"}
                    </td>
                    <td className="py-1.5 pr-3">
                      {exp.metrics ? formatMetric(exp.metrics.f1Score) : "—"}
                    </td>
                    <td className="py-1.5 pr-3">
                      {exp.metrics ? formatMetric(exp.metrics.precision) : "—"}
                    </td>
                    <td className="py-1.5">
                      {exp.metrics ? formatMetric(exp.metrics.mcc) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AnalysisPanelContainer>
  );
}
