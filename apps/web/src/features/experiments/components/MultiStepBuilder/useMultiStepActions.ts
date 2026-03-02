import { useCallback } from "react";
import type {
  CombineOperator,
  EnrichmentAnalysisType,
  PlanStepNode,
  StrategyStep,
} from "@pathfinder/shared";
import { useExperimentViewStore, useExperimentRunStore } from "../../store";
import { generateStepId } from "./multiStepUtils";
import type { MultiStepState } from "./useMultiStepState";

export interface MultiStepActions {
  addSearchStep: (searchName: string, displayName: string) => void;
  addCombineStep: (
    primaryId: string,
    secondaryId: string,
    operator: CombineOperator,
  ) => void;
  updateStep: (stepId: string, updates: Partial<StrategyStep>) => void;
  removeStep: (stepId: string) => void;
  loadImportedSteps: (steps: StrategyStep[], importRecordType?: string) => void;
  handleRecordTypeChange: (rt: string) => void;
  toggleEnrichment: (type: EnrichmentAnalysisType) => void;
  handleRun: () => void;
  refreshCounts: () => void;
  goBack: () => void;
}

export function useMultiStepActions(
  siteId: string,
  state: MultiStepState,
  canRun: boolean,
  stepTree: PlanStepNode | null,
): MultiStepActions {
  const { setView } = useExperimentViewStore();
  const { runExperiment, runBenchmark, clearError } = useExperimentRunStore();

  // Destructure state to satisfy React Compiler and exhaustive-deps rules.
  // Each destructured value is a stable reference (either a primitive or a
  // setState function), so dependency arrays stay minimal and correct.
  const {
    selectedRecordType,
    setStepsById,
    setSelectedStepId,
    setSelectedRecordType,
    setEnrichments,
    setRefreshKey,
    steps,
    strategy,
    positiveControls,
    negativeControls,
    controlsSearchName,
    controlsParamName,
    enableCV,
    kFolds,
    enrichments,
    name,
    stepAnalysis,
    sortAttribute,
    sortDirection,
    benchmarkMode,
    benchmarkControlSets,
  } = state;

  const addSearchStep = useCallback(
    (searchName: string, displayName: string) => {
      const id = generateStepId();
      const step: StrategyStep = {
        id,
        displayName,
        searchName,
        recordType: selectedRecordType,
        parameters: {},
      };
      setStepsById((prev) => ({ ...prev, [id]: step }));
      setSelectedStepId(id);
    },
    [selectedRecordType, setStepsById, setSelectedStepId],
  );

  const addCombineStep = useCallback(
    (primaryId: string, secondaryId: string, operator: CombineOperator) => {
      const id = generateStepId();
      const step: StrategyStep = {
        id,
        displayName: `${operator} combine`,
        searchName: `boolean_question_${operator.toLowerCase()}`,
        recordType: selectedRecordType,
        operator,
        primaryInputStepId: primaryId,
        secondaryInputStepId: secondaryId,
        parameters: {},
      };
      setStepsById((prev) => ({ ...prev, [id]: step }));
    },
    [selectedRecordType, setStepsById],
  );

  const updateStep = useCallback(
    (stepId: string, updates: Partial<StrategyStep>) => {
      setStepsById((prev) => {
        const existing = prev[stepId];
        if (!existing) return prev;
        return { ...prev, [stepId]: { ...existing, ...updates } };
      });
    },
    [setStepsById],
  );

  const removeStep = useCallback(
    (stepId: string) => {
      setStepsById((prev) => {
        const next = { ...prev };
        delete next[stepId];

        const combineIds = Object.keys(next).filter(
          (id) =>
            next[id].primaryInputStepId === stepId ||
            next[id].secondaryInputStepId === stepId,
        );

        for (const id of combineIds) {
          const step = next[id];
          const losePrimary = step.primaryInputStepId === stepId;
          const loseSecondary = step.secondaryInputStepId === stepId;

          if (losePrimary && loseSecondary) {
            delete next[id];
          } else if (losePrimary && step.secondaryInputStepId) {
            const remaining = step.secondaryInputStepId;
            delete next[id];
            for (const [otherId, otherStep] of Object.entries(next)) {
              if (otherStep.primaryInputStepId === id)
                next[otherId] = { ...otherStep, primaryInputStepId: remaining };
              if (otherStep.secondaryInputStepId === id)
                next[otherId] = { ...otherStep, secondaryInputStepId: remaining };
            }
          } else if (loseSecondary && step.primaryInputStepId) {
            const remaining = step.primaryInputStepId;
            delete next[id];
            for (const [otherId, otherStep] of Object.entries(next)) {
              if (otherStep.primaryInputStepId === id)
                next[otherId] = { ...otherStep, primaryInputStepId: remaining };
              if (otherStep.secondaryInputStepId === id)
                next[otherId] = { ...otherStep, secondaryInputStepId: remaining };
            }
          } else {
            delete next[id];
          }
        }

        return next;
      });
      setSelectedStepId((prev) => (prev === stepId ? null : prev));
    },
    [setStepsById, setSelectedStepId],
  );

  const loadImportedSteps = useCallback(
    (importedSteps: StrategyStep[], importRecordType?: string) => {
      const rt = importRecordType || selectedRecordType;
      if (importRecordType) {
        setSelectedRecordType(importRecordType);
      }
      const newSteps: Record<string, StrategyStep> = {};
      for (const step of importedSteps) {
        newSteps[step.id] = { ...step, recordType: step.recordType || rt };
      }
      setStepsById(newSteps);
    },
    [selectedRecordType, setStepsById, setSelectedRecordType],
  );

  const handleRecordTypeChange = useCallback(
    (rt: string) => {
      setSelectedRecordType(rt);
      setStepsById({});
    },
    [setSelectedRecordType, setStepsById],
  );

  const toggleEnrichment = useCallback(
    (type: EnrichmentAnalysisType) => {
      setEnrichments((prev) => {
        const next = new Set(prev);
        if (next.has(type)) next.delete(type);
        else next.add(type);
        return next;
      });
    },
    [setEnrichments],
  );

  const handleRun = useCallback(() => {
    if (!canRun || !stepTree) return;
    clearError();

    const rootStep = steps.find((s) => s.id === strategy?.rootStepId);

    const cleanIds = (ids: string[]) => ids.map((s) => s.trim()).filter(Boolean);

    const config = {
      siteId,
      recordType: selectedRecordType,
      mode: "multi-step" as const,
      searchName: rootStep?.searchName ?? steps[0]?.searchName ?? "",
      parameters: rootStep?.parameters ?? {},
      stepTree,
      positiveControls: cleanIds(positiveControls),
      negativeControls: cleanIds(negativeControls),
      controlsSearchName,
      controlsParamName,
      controlsValueFormat: "newline",
      enableCrossValidation: enableCV,
      kFolds: Math.max(2, Math.min(10, kFolds)),
      enrichmentTypes: Array.from(enrichments) as EnrichmentAnalysisType[],
      name: name || "Multi-step experiment",
      enableStepAnalysis: stepAnalysis.enabled,
      stepAnalysisPhases: stepAnalysis.enabled
        ? Array.from(stepAnalysis.phases)
        : undefined,
      ...(sortAttribute ? { sortAttribute, sortDirection } : {}),
    };

    if (benchmarkMode && benchmarkControlSets.length > 0) {
      const cleanedSets = benchmarkControlSets.map((cs) => ({
        ...cs,
        positiveControls: cleanIds(cs.positiveControls),
        negativeControls: cleanIds(cs.negativeControls),
      }));
      runBenchmark(config, cleanedSets);
    } else {
      runExperiment(config);
    }
  }, [
    canRun,
    stepTree,
    strategy?.rootStepId,
    steps,
    siteId,
    selectedRecordType,
    positiveControls,
    negativeControls,
    controlsSearchName,
    controlsParamName,
    enableCV,
    kFolds,
    enrichments,
    name,
    stepAnalysis,
    sortAttribute,
    sortDirection,
    benchmarkMode,
    benchmarkControlSets,
    runExperiment,
    runBenchmark,
    clearError,
  ]);

  const refreshCounts = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, [setRefreshKey]);

  const goBack = useCallback(() => {
    setView("mode-select");
  }, [setView]);

  return {
    addSearchStep,
    addCombineStep,
    updateStep,
    removeStep,
    loadImportedSteps,
    handleRecordTypeChange,
    toggleEnrichment,
    handleRun,
    refreshCounts,
    goBack,
  };
}
