"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { Target, Play, Loader2 } from "lucide-react";
import type { Experiment, EnrichmentAnalysisType } from "@pathfinder/shared";
import { Button } from "@/lib/components/ui/Button";
import type { OperationSubscription } from "@/lib/operationSubscribe";
import {
  MetricsOverview,
  ConfusionMatrixSection,
  CrossValidationSection,
  GeneListsSection,
  EnrichmentSection,
  RobustnessSection,
  RankMetricsSection,
} from "@/features/analysis";
import {
  createExperimentStream,
  type ExperimentSSEHandler,
} from "@/features/workbench/api";
import { CONTROLS_SEARCH_NAME, CONTROLS_PARAM_NAME } from "../../constants";
import { AnalysisPanelContainer } from "../AnalysisPanelContainer";
import { GeneChipInput } from "../GeneChipInput";
import { SaveControlSetForm } from "../SaveControlSetForm";
import { ControlSetQuickPick } from "../ControlSetQuickPick";
import { useWorkbenchStore } from "../../store";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EvaluatePanel() {
  const geneSets = useWorkbenchStore((s) => s.geneSets);
  const activeSetId = useWorkbenchStore((s) => s.activeSetId);
  const activeSet = geneSets.find((gs) => gs.id === activeSetId);
  const setLastExperiment = useWorkbenchStore((s) => s.setLastExperiment);

  const [positiveControls, setPositiveControls] = useState<string[]>([]);
  const [negativeControls, setNegativeControls] = useState<string[]>([]);
  const [enableCV, setEnableCV] = useState(false);
  const [kFolds, setKFolds] = useState(5);
  const [enableStepAnalysis, setEnableStepAnalysis] = useState(false);
  const [enrichmentTypes, setEnrichmentTypes] = useState<EnrichmentAnalysisType[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const subscriptionRef = useRef<OperationSubscription | null>(null);

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
        setPositiveControls((prev) => [...prev, ...pos]);
      }
      if (neg.length > 0) {
        setNegativeControls((prev) => [...prev, ...neg]);
      }
    });
  }, [pendingPositive, pendingNegative, clearPendingControls]);

  useEffect(() => {
    return () => {
      subscriptionRef.current?.unsubscribe();
    };
  }, []);

  const hasSearchContext = Boolean(
    activeSet != null &&
    (activeSet.geneIds.length > 0 ||
      (activeSet.searchName != null &&
        activeSet.searchName !== "" &&
        activeSet.parameters != null)),
  );

  const handleRun = useCallback(async () => {
    if (!activeSet) return;
    const hasGeneIds = activeSet.geneIds.length > 0;
    const hasSearch =
      activeSet.searchName != null &&
      activeSet.searchName !== "" &&
      activeSet.parameters != null;
    if (!hasGeneIds && !hasSearch) return;
    if (positiveControls.length === 0) {
      setError("At least one positive control gene ID is required.");
      return;
    }

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
      const evalConfig: Parameters<typeof createExperimentStream>[0] = {
        siteId: activeSet.siteId,
        recordType: activeSet.recordType ?? "gene",
        searchName: activeSet.searchName ?? "",
        parameters: activeSet.parameters ?? {},
        positiveControls,
        negativeControls,
        controlsSearchName: CONTROLS_SEARCH_NAME,
        controlsParamName: CONTROLS_PARAM_NAME,
        controlsValueFormat: "newline",
        enableCrossValidation: enableCV,
        kFolds,
        enableStepAnalysis,
        enrichmentTypes,
        name: `Workbench eval: ${activeSet.name}`,
      };
      if (activeSet.geneIds.length > 0) evalConfig.targetGeneIds = activeSet.geneIds;
      const subscription = await createExperimentStream(evalConfig, handlers);
      subscriptionRef.current = subscription;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    }
  }, [
    activeSet,
    activeSetId,
    positiveControls,
    negativeControls,
    enableCV,
    kFolds,
    enableStepAnalysis,
    enrichmentTypes,
    setLastExperiment,
  ]);

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
        {/* Quick pick from saved controls */}
        {activeSet?.siteId != null && activeSet.siteId !== "" && (
          <ControlSetQuickPick
            siteId={activeSet.siteId}
            onSelect={(posIds, negIds) => {
              setPositiveControls(posIds);
              setNegativeControls(negIds);
            }}
          />
        )}

        {/* Controls form */}
        <div className="grid gap-4 sm:grid-cols-2">
          <GeneChipInput
            siteId={activeSet?.siteId ?? ""}
            value={positiveControls}
            onChange={setPositiveControls}
            label="Positive Controls"
            tint="positive"
            required
          />
          <GeneChipInput
            siteId={activeSet?.siteId ?? ""}
            value={negativeControls}
            onChange={setNegativeControls}
            label="Negative Controls"
            tint="negative"
          />
        </div>

        {/* Save controls as reusable set */}
        <SaveControlSetForm
          siteId={activeSet?.siteId ?? ""}
          positiveIds={positiveControls}
          negativeIds={negativeControls}
        />

        {/* Analysis options */}
        <div className="space-y-3">
          <p className="text-xs font-medium text-muted-foreground">Analysis Options</p>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={enableCV}
              onChange={(e) => setEnableCV(e.target.checked)}
              className="rounded border-input"
            />
            Cross-validation ({kFolds}-fold)
          </label>
          {enableCV && (
            <div className="flex items-center gap-2 pl-5">
              <span className="text-[10px] text-muted-foreground">2</span>
              <input
                type="range"
                min={2}
                max={10}
                value={kFolds}
                onChange={(e) => setKFolds(Number(e.target.value))}
                className="h-1.5 w-24 accent-primary"
              />
              <span className="text-[10px] text-muted-foreground">10</span>
            </div>
          )}
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={enableStepAnalysis}
              onChange={(e) => setEnableStepAnalysis(e.target.checked)}
              className="rounded border-input"
            />
            Step contribution analysis
          </label>
          <div className="flex flex-wrap gap-1.5">
            {(["go_process", "go_function", "go_component", "pathway"] as const).map(
              (t) => {
                const label = {
                  go_process: "GO:BP",
                  go_function: "GO:MF",
                  go_component: "GO:CC",
                  pathway: "Pathway",
                }[t];
                const active = enrichmentTypes.includes(t);
                return (
                  <button
                    key={t}
                    type="button"
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-medium border transition-colors ${
                      active
                        ? "bg-primary text-primary-foreground border-primary"
                        : "border-input text-muted-foreground hover:border-foreground/30"
                    }`}
                    onClick={() =>
                      setEnrichmentTypes((prev) =>
                        active ? prev.filter((x) => x !== t) : [...prev, t],
                      )
                    }
                  >
                    {label}
                  </button>
                );
              },
            )}
          </div>
        </div>

        {/* Run button */}
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
          {loading ? "Evaluating..." : "Run Evaluation"}
        </Button>

        {error != null && error !== "" && (
          <p className="text-xs text-destructive">{error}</p>
        )}

        {/* Results */}
        {experiment?.metrics != null && (
          <div className="space-y-6">
            <MetricsOverview
              metrics={experiment.metrics}
              rankMetrics={experiment.rankMetrics ?? null}
              robustness={experiment.robustness ?? null}
            />
            <ConfusionMatrixSection cm={experiment.metrics.confusionMatrix} />
            {experiment.rankMetrics && (
              <RankMetricsSection rankMetrics={experiment.rankMetrics} />
            )}
            {experiment.robustness && (
              <RobustnessSection robustness={experiment.robustness} />
            )}
            {experiment.crossValidation && (
              <CrossValidationSection cv={experiment.crossValidation} />
            )}
            {(experiment.enrichmentResults?.length ?? 0) > 0 && (
              <EnrichmentSection results={experiment.enrichmentResults ?? []} />
            )}
            <GeneListsSection experiment={experiment} />
          </div>
        )}
      </div>
    </AnalysisPanelContainer>
  );
}
