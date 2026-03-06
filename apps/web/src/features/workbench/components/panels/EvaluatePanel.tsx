"use client";

import { useState, useCallback, useEffect } from "react";
import { Target, Play, Loader2 } from "lucide-react";
import type { Experiment } from "@pathfinder/shared";
import { Button } from "@/lib/components/ui/Button";
import {
  MetricsOverview,
  ConfusionMatrixSection,
  GeneListsSection,
} from "@/features/analysis";
import {
  createExperimentStream,
  type ExperimentSSEHandler,
} from "@/features/workbench/api";
import { AnalysisPanelContainer } from "../AnalysisPanelContainer";
import { useWorkbenchStore } from "../../store";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EvaluatePanel() {
  const geneSets = useWorkbenchStore((s) => s.geneSets);
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);
  const activeSet = geneSets.find((gs) => gs.id === activeSetId);
  const setLastExperiment = useWorkbenchStore((s) => s.setLastExperiment);

  const [positiveControls, setPositiveControls] = useState("");
  const [negativeControls, setNegativeControls] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [experiment, setExperiment] = useState<Experiment | null>(null);

  // Consume pending controls from gene search sidebar
  const pendingPositive = useWorkbenchStore((s) => s.pendingPositiveControls);
  const pendingNegative = useWorkbenchStore((s) => s.pendingNegativeControls);
  const clearPendingControls = useWorkbenchStore((s) => s.clearPendingControls);

  useEffect(() => {
    if (pendingPositive.length === 0 && pendingNegative.length === 0) return;
    const pos = pendingPositive;
    const neg = pendingNegative;
    clearPendingControls();
    queueMicrotask(() => {
      if (pos.length > 0) {
        setPositiveControls((prev) => {
          const existing = prev.trim();
          const joined = pos.join("\n");
          return existing ? `${existing}\n${joined}` : joined;
        });
      }
      if (neg.length > 0) {
        setNegativeControls((prev) => {
          const existing = prev.trim();
          const joined = neg.join("\n");
          return existing ? `${existing}\n${joined}` : joined;
        });
      }
    });
  }, [pendingPositive, pendingNegative, clearPendingControls]);

  const hasSearchContext = Boolean(activeSet?.searchName && activeSet.parameters);

  const handleRun = useCallback(async () => {
    if (!activeSet || !activeSet.searchName || !activeSet.parameters) return;
    const posLines = positiveControls
      .split(/[\n,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (posLines.length === 0) {
      setError("At least one positive control gene ID is required.");
      return;
    }
    const negLines = negativeControls
      .split(/[\n,]+/)
      .map((s) => s.trim())
      .filter(Boolean);

    setLoading(true);
    setError(null);
    setExperiment(null);

    const handlers: ExperimentSSEHandler = {
      onComplete: (data) => {
        setExperiment(data);
        setLastExperiment(data, activeSetId ?? null);
        setLoading(false);
      },
      onError: (errMsg) => {
        setError(errMsg);
        setLoading(false);
      },
    };

    try {
      await createExperimentStream(
        {
          siteId: activeSet.siteId,
          recordType: activeSet.recordType ?? "gene",
          searchName: activeSet.searchName,
          parameters: activeSet.parameters,
          positiveControls: posLines,
          negativeControls: negLines,
          controlsSearchName: "GeneByLocusTag",
          controlsParamName: "ds_gene_ids",
          controlsValueFormat: "newline",
          enableCrossValidation: false,
          kFolds: 5,
          enrichmentTypes: [],
          name: `Workbench eval: ${activeSet.name}`,
        },
        handlers,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    }
  }, [activeSet, activeSetId, positiveControls, negativeControls, setLastExperiment]);

  return (
    <AnalysisPanelContainer
      panelId="evaluate"
      title="Evaluate Strategy"
      subtitle="Test strategy performance against known gene sets"
      icon={<Target className="h-4 w-4" />}
      disabled={!hasSearchContext}
      disabledReason="Requires a strategy-backed gene set with search parameters"
    >
      <div className="space-y-4">
        {/* Controls form */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Positive Controls (required)
            </label>
            <textarea
              value={positiveControls}
              onChange={(e) => setPositiveControls(e.target.value)}
              placeholder="Paste gene IDs, one per line or comma-separated"
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Negative Controls (optional)
            </label>
            <textarea
              value={negativeControls}
              onChange={(e) => setNegativeControls(e.target.value)}
              placeholder="Paste gene IDs, one per line or comma-separated"
              rows={4}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
        </div>

        {/* Run button */}
        <Button size="sm" onClick={handleRun} disabled={loading}>
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Play className="h-3.5 w-3.5" />
          )}
          {loading ? "Evaluating..." : "Run Evaluation"}
        </Button>

        {error && <p className="text-xs text-destructive">{error}</p>}

        {/* Results */}
        {experiment && experiment.metrics && (
          <div className="space-y-6">
            <MetricsOverview
              metrics={experiment.metrics}
              rankMetrics={experiment.rankMetrics}
              robustness={experiment.robustness}
            />
            <ConfusionMatrixSection cm={experiment.metrics.confusionMatrix} />
            <GeneListsSection experiment={experiment} />
          </div>
        )}
      </div>
    </AnalysisPanelContainer>
  );
}
