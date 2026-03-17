"use client";

import { useState, useCallback, useEffect } from "react";
import { Layers, Play, Loader2 } from "lucide-react";
import type { Experiment } from "@pathfinder/shared";
import { Button } from "@/lib/components/ui/Button";
import { Label } from "@/lib/components/ui/Label";
import { SearchableMultiSelect } from "@/lib/components/ui/SearchableMultiSelect";
import { listOrganisms } from "@/lib/api/genes";
import {
  createBatchExperimentStream,
  type BatchOrganismTarget,
} from "@/features/workbench/api";
import { CONTROLS_SEARCH_NAME, CONTROLS_PARAM_NAME } from "../../constants";
import { AnalysisPanelContainer } from "../AnalysisPanelContainer";
import { GeneChipInput } from "../GeneChipInput";
import { ParamNameSelect } from "../ParamNameSelect";
import { useWorkbenchStore } from "../../store";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function BatchPanel() {
  const geneSets = useWorkbenchStore((s) => s.geneSets);
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);
  const activeSet = geneSets.find((gs) => gs.id === activeSetId);

  const [selectedOrganisms, setSelectedOrganisms] = useState<string[]>([]);
  const [organismParamName, setOrganismParamName] = useState<string | null>(null);
  const [positiveControls, setPositiveControls] = useState<string[]>([]);
  const [negativeControls, setNegativeControls] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Experiment[] | null>(null);
  const [expectedCount, setExpectedCount] = useState(0);
  const [batchParamName, setBatchParamName] = useState<string | null>(null);

  // Fetch organisms for SearchableMultiSelect
  const [availableOrganisms, setAvailableOrganisms] = useState<string[]>([]);
  const [organismsLoading, setOrganismsLoading] = useState(false);

  useEffect(() => {
    if (!activeSet?.siteId) return;
    let cancelled = false;
    // Defer so setState runs outside the effect body (avoids cascading renders)
    queueMicrotask(() => {
      if (!cancelled) setOrganismsLoading(true);
    });
    listOrganisms(activeSet.siteId)
      .then((orgs) => {
        if (!cancelled) setAvailableOrganisms(orgs);
      })
      .finally(() => {
        if (!cancelled) setOrganismsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeSet?.siteId]);

  const hasSearchContext = Boolean(activeSet?.searchName && activeSet.parameters);

  const handleRun = useCallback(async () => {
    if (!activeSet) return;
    if (selectedOrganisms.length === 0) return;
    if (!organismParamName) return;

    setBatchParamName(organismParamName);

    const targets: BatchOrganismTarget[] = selectedOrganisms.map((org) => ({
      organism: org,
      positiveControls: positiveControls.length > 0 ? positiveControls : null,
      negativeControls: negativeControls.length > 0 ? negativeControls : null,
    }));

    setLoading(true);
    setError(null);
    setResults(null);
    setExpectedCount(selectedOrganisms.length);

    try {
      await createBatchExperimentStream(
        {
          siteId: activeSet.siteId,
          recordType: activeSet.recordType ?? "gene",
          searchName: activeSet.searchName ?? "",
          parameters: activeSet.parameters ?? {},
          positiveControls,
          negativeControls,
          controlsSearchName: CONTROLS_SEARCH_NAME,
          controlsParamName: CONTROLS_PARAM_NAME,
          controlsValueFormat: "newline",
          enableCrossValidation: false,
          kFolds: 5,
          enrichmentTypes: [],
          name: `Batch: ${activeSet.name}`,
        },
        organismParamName,
        targets,
        {
          onComplete: (experiments) => {
            setResults(experiments);
            setLoading(false);
          },
          onError: (errMsg) => {
            setError(errMsg);
            setLoading(false);
          },
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    }
  }, [
    activeSet,
    selectedOrganisms,
    organismParamName,
    positiveControls,
    negativeControls,
  ]);

  return (
    <AnalysisPanelContainer
      panelId="batch"
      title="Batch Evaluation"
      subtitle="Evaluate strategy across multiple organisms"
      icon={<Layers className="h-4 w-4" />}
      disabled={!hasSearchContext}
      disabledReason="Requires a strategy-backed gene set with search parameters"
    >
      <div className="space-y-4">
        {/* Organism multi-select */}
        <div>
          <Label className="mb-1 block text-xs text-muted-foreground">
            Target Organisms
          </Label>
          <SearchableMultiSelect
            options={availableOrganisms.map((org) => ({
              value: org,
              label: org,
            }))}
            selected={selectedOrganisms}
            onChange={setSelectedOrganisms}
            placeholder="Select target organisms"
            loading={organismsLoading}
          />
        </div>

        {/* Organism param name */}
        <div>
          <Label className="mb-1 block text-xs text-muted-foreground">
            Organism Parameter Name
          </Label>
          <ParamNameSelect
            siteId={activeSet?.siteId ?? ""}
            recordType={activeSet?.recordType ?? "gene"}
            searchName={activeSet?.searchName ?? ""}
            value={organismParamName}
            onChange={setOrganismParamName}
            placeholder="Select parameter"
          />
        </div>

        {/* Shared controls */}
        <div className="grid gap-4 sm:grid-cols-2">
          <GeneChipInput
            siteId={activeSet?.siteId ?? ""}
            value={positiveControls}
            onChange={setPositiveControls}
            label="Shared Positive Controls"
            tint="positive"
          />
          <GeneChipInput
            siteId={activeSet?.siteId ?? ""}
            value={negativeControls}
            onChange={setNegativeControls}
            label="Shared Negative Controls"
            tint="negative"
          />
        </div>

        {/* Run button */}
        <Button size="sm" onClick={handleRun} disabled={loading}>
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Play className="h-3.5 w-3.5" />
          )}
          {loading ? "Running..." : "Run Batch"}
        </Button>

        {error && <p className="text-xs text-destructive">{error}</p>}

        {/* Results table */}
        {results && results.length > 0 && (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">
                    Organism
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-muted-foreground">
                    Sensitivity
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-muted-foreground">
                    Specificity
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-muted-foreground">
                    F1
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-muted-foreground">
                    Result Count
                  </th>
                </tr>
              </thead>
              <tbody>
                {results.map((exp) => {
                  const paramKey = batchParamName;
                  const orgValue =
                    (paramKey ? exp.config.parameters?.[paramKey] : undefined) ??
                    exp.config.name;
                  return (
                    <tr key={exp.id} className="border-b last:border-b-0">
                      <td className="px-3 py-2 text-foreground">{String(orgValue)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {exp.metrics?.sensitivity?.toFixed(3) ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {exp.metrics?.specificity?.toFixed(3) ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {exp.metrics?.f1Score?.toFixed(3) ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {exp.metrics?.totalResults ?? "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {results && results.length > 0 && results.length < expectedCount && (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            Completed {results.length} of {expectedCount} organisms. Some organisms may
            have failed.
          </p>
        )}
      </div>
    </AnalysisPanelContainer>
  );
}
