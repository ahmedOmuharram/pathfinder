import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  CombineOperator,
  EnrichmentAnalysisType,
  ExperimentConfig,
  PlanStepNode,
  RecordType,
  Search,
  StrategyPlan,
} from "@pathfinder/shared";
import type { TreeOptimizationConfig } from "./ConfigPanel";
import type { StrategyStep, StrategyWithMeta } from "@/features/strategy/types";
import { useExperimentStore } from "../../store";
import { getRecordTypes, getSearches, computeStepCounts } from "@/lib/api/client";
import { getRootStepId, serializeStrategyPlan } from "@/lib/strategyGraph";
import { useStepCounts } from "@/features/strategy/services/useStepCounts";
import type { ResolvedGene } from "@/lib/api/client";
import { GENE_RECORD_TYPES } from "../SetupWizard/constants";

function generateStepId(): string {
  return `step_${Math.random().toString(16).slice(2, 10)}`;
}

function buildLocalStrategy(
  stepsById: Record<string, StrategyStep>,
  siteId: string,
  recordType: string,
): StrategyWithMeta | null {
  const steps = Object.values(stepsById);
  if (steps.length === 0) return null;
  const rootStepId = getRootStepId(steps);
  return {
    id: "experiment-draft",
    name: "Experiment Strategy",
    siteId,
    recordType,
    steps,
    rootStepId,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

const DEFAULT_TREE_OPT: TreeOptimizationConfig = {
  enabled: false,
  budget: 20,
  objective: "balanced_accuracy",
  optimizeOperators: true,
  optimizeOrthologs: false,
  optimizeStructure: false,
};

function flattenPlanStepNode(node: PlanStepNode, recordType: string): StrategyStep[] {
  const steps: StrategyStep[] = [];
  const id = node.id ?? `step_${Math.random().toString(16).slice(2, 10)}`;
  const params: Record<string, string> = {};
  if (node.parameters) {
    for (const [k, v] of Object.entries(node.parameters)) {
      params[k] = String(v ?? "");
    }
  }

  let primaryInputStepId: string | undefined;
  let secondaryInputStepId: string | undefined;

  if (node.primaryInput) {
    const childSteps = flattenPlanStepNode(node.primaryInput, recordType);
    steps.push(...childSteps);
    primaryInputStepId = childSteps[childSteps.length - 1]?.id;
  }
  if (node.secondaryInput) {
    const childSteps = flattenPlanStepNode(node.secondaryInput, recordType);
    steps.push(...childSteps);
    secondaryInputStepId = childSteps[childSteps.length - 1]?.id;
  }

  steps.push({
    id,
    displayName: node.displayName ?? node.searchName,
    searchName: node.searchName,
    recordType,
    parameters: params,
    operator: node.operator as CombineOperator | undefined,
    primaryInputStepId,
    secondaryInputStepId,
  });

  return steps;
}

function applyMultiStepClone(
  config: ExperimentConfig,
  setters: {
    setName: (v: string) => void;
    setSelectedRecordType: (v: string) => void;
    setPositiveGenes: (v: ResolvedGene[]) => void;
    setNegativeGenes: (v: ResolvedGene[]) => void;
    setEnableCV: (v: boolean) => void;
    setKFolds: (v: number) => void;
    setKFoldsDraft: (v: string) => void;
    setEnrichments: (v: Set<EnrichmentAnalysisType>) => void;
    loadImportedSteps: (steps: StrategyStep[], rt?: string) => void;
    setTreeOpt: (v: TreeOptimizationConfig) => void;
  },
  enableOptimize: boolean,
) {
  setters.setName(`${config.name} (clone)`);
  setters.setSelectedRecordType(config.recordType);
  setters.setEnableCV(config.enableCrossValidation);
  setters.setKFolds(config.kFolds);
  setters.setKFoldsDraft(String(config.kFolds));
  setters.setEnrichments(new Set(config.enrichmentTypes));

  const toResolved = (ids: string[]): ResolvedGene[] =>
    ids.map((id) => ({
      geneId: id,
      displayName: id,
      organism: "",
      product: "",
      geneName: "",
      geneType: "",
      location: "",
    }));
  setters.setPositiveGenes(toResolved(config.positiveControls));
  setters.setNegativeGenes(toResolved(config.negativeControls));

  if (config.stepTree) {
    const steps = flattenPlanStepNode(config.stepTree, config.recordType);
    setters.loadImportedSteps(steps, config.recordType);
  }

  const shouldEnableOpt = enableOptimize || config.enableTreeOptimization === true;
  setters.setTreeOpt({
    enabled: shouldEnableOpt,
    budget: config.treeOptimizationBudget ?? 20,
    objective: config.optimizationObjective ?? "balanced_accuracy",
    optimizeOperators: config.optimizeOperators ?? true,
    optimizeOrthologs: config.optimizeOrthologs ?? false,
    optimizeStructure: config.optimizeStructure ?? false,
  });
}

export function useMultiStepBuilder(siteId: string) {
  const {
    runExperiment,
    setView,
    isRunning,
    error: storeError,
    clearError,
    cloneConfig,
    cloneWithOptimize,
    clearClone,
  } = useExperimentStore();

  const [stepsById, setStepsById] = useState<Record<string, StrategyStep>>({});
  const [allRecordTypes, setAllRecordTypes] = useState<RecordType[]>([]);
  const [searches, setSearches] = useState<Search[]>([]);
  const [selectedRecordType, setSelectedRecordType] = useState("transcript");
  const [searchFilter, setSearchFilter] = useState("");

  const [positiveGenes, setPositiveGenes] = useState<ResolvedGene[]>([]);
  const [negativeGenes, setNegativeGenes] = useState<ResolvedGene[]>([]);
  const [showGeneLookup, setShowGeneLookup] = useState(false);

  const [refreshKey, setRefreshKey] = useState(0);

  const [name, setName] = useState("");
  const [enableCV, setEnableCV] = useState(false);
  const [kFolds, setKFolds] = useState(5);
  const [kFoldsDraft, setKFoldsDraft] = useState("5");
  const [enrichments, setEnrichments] = useState<Set<EnrichmentAnalysisType>>(
    new Set(),
  );
  const [treeOpt, setTreeOpt] = useState<TreeOptimizationConfig>(DEFAULT_TREE_OPT);
  const controlsSearchName = "GeneByLocusTag";
  const controlsParamName = "ds_gene_ids";

  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [importModalOpen, setImportModalOpen] = useState(false);

  const recordTypes = useMemo(
    () => allRecordTypes.filter((rt) => GENE_RECORD_TYPES.has(rt.name)),
    [allRecordTypes],
  );

  const filteredSearches = useMemo(
    () =>
      searches.filter(
        (s) =>
          !searchFilter ||
          s.displayName.toLowerCase().includes(searchFilter.toLowerCase()) ||
          s.name.toLowerCase().includes(searchFilter.toLowerCase()),
      ),
    [searches, searchFilter],
  );

  const positiveControls = useMemo(
    () => positiveGenes.map((g) => g.geneId),
    [positiveGenes],
  );
  const negativeControls = useMemo(
    () => negativeGenes.map((g) => g.geneId),
    [negativeGenes],
  );

  const steps = useMemo(() => Object.values(stepsById), [stepsById]);

  const strategy = useMemo(
    () => buildLocalStrategy(stepsById, siteId, selectedRecordType),
    [stepsById, siteId, selectedRecordType],
  );

  const planResult = useMemo(() => {
    if (!strategy) return null;
    return serializeStrategyPlan(stepsById, strategy);
  }, [stepsById, strategy]);

  const planHash = planResult ? JSON.stringify(planResult.plan) : null;

  const stepCountsRef = useRef<Record<string, number | null | undefined>>({});
  const setStepCounts = useCallback(
    (counts: Record<string, number | null | undefined>) => {
      stepCountsRef.current = counts;
      setStepsById((prev) => {
        let changed = false;
        const next = { ...prev };
        for (const [stepId, count] of Object.entries(counts)) {
          const step = next[stepId];
          if (!step) continue;
          const nextCount =
            typeof count === "number" || count === null ? count : undefined;
          // Don't overwrite a real count with undefined (loading) or null (?).
          // This preserves WDK estimatedSize values from import until a real
          // computed count arrives.
          if (typeof step.resultCount === "number" && typeof nextCount !== "number") {
            continue;
          }
          if (step.resultCount !== nextCount) {
            next[stepId] = { ...step, resultCount: nextCount };
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    },
    [],
  );

  useStepCounts({
    siteId,
    plan: planResult?.plan ?? null,
    planHash,
    stepIds: steps.map((s) => s.id),
    setStepCounts,
    fetchCounts: computeStepCounts,
    refreshKey,
  });

  useEffect(() => {
    getRecordTypes(siteId)
      .then(setAllRecordTypes)
      .catch(() => {});
  }, [siteId]);

  useEffect(() => {
    getSearches(siteId, selectedRecordType)
      .then(setSearches)
      .catch(() => {});
  }, [siteId, selectedRecordType]);

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
    [selectedRecordType],
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
    [selectedRecordType],
  );

  const updateStep = useCallback((stepId: string, updates: Partial<StrategyStep>) => {
    setStepsById((prev) => {
      const existing = prev[stepId];
      if (!existing) return prev;
      return { ...prev, [stepId]: { ...existing, ...updates } };
    });
  }, []);

  const removeStep = useCallback((stepId: string) => {
    setStepsById((prev) => {
      const next = { ...prev };
      delete next[stepId];
      for (const [id, step] of Object.entries(next)) {
        if (
          step.primaryInputStepId === stepId ||
          step.secondaryInputStepId === stepId
        ) {
          const patch: Partial<StrategyStep> = {};
          if (step.primaryInputStepId === stepId) patch.primaryInputStepId = undefined;
          if (step.secondaryInputStepId === stepId)
            patch.secondaryInputStepId = undefined;
          next[id] = { ...step, ...patch };
        }
      }
      return next;
    });
    setSelectedStepId((prev) => (prev === stepId ? null : prev));
  }, []);

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
    [selectedRecordType],
  );

  useEffect(() => {
    if (!cloneConfig) return;
    if (cloneConfig.mode !== "multi-step" && cloneConfig.mode !== "import") return;
    applyMultiStepClone(
      cloneConfig,
      {
        setName,
        setSelectedRecordType,
        setPositiveGenes,
        setNegativeGenes,
        setEnableCV,
        setKFolds,
        setKFoldsDraft,
        setEnrichments,
        loadImportedSteps,
        setTreeOpt,
      },
      cloneWithOptimize,
    );
    clearClone();
  }, [cloneConfig, cloneWithOptimize, clearClone, loadImportedSteps]);

  const handleRecordTypeChange = useCallback((rt: string) => {
    setSelectedRecordType(rt);
    setStepsById({});
  }, []);

  const toggleEnrichment = useCallback((type: EnrichmentAnalysisType) => {
    setEnrichments((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  const stepTree = useMemo((): PlanStepNode | null => {
    if (!planResult) return null;
    return planResult.plan.root;
  }, [planResult]);

  const canRun = useMemo(() => {
    if (steps.length === 0) return false;
    if (positiveControls.length === 0 && negativeControls.length === 0) return false;
    if (!planResult) return false;
    return true;
  }, [steps.length, positiveControls.length, negativeControls.length, planResult]);

  const refreshCounts = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  const handleRun = useCallback(() => {
    if (!canRun || !stepTree) return;
    clearError();

    const rootStep = steps.find((s) => s.id === strategy?.rootStepId);

    const config = {
      siteId,
      recordType: selectedRecordType,
      mode: "multi-step" as const,
      searchName: rootStep?.searchName ?? steps[0]?.searchName ?? "",
      parameters: rootStep?.parameters ?? {},
      stepTree,
      positiveControls,
      negativeControls,
      controlsSearchName,
      controlsParamName,
      controlsValueFormat: "newline",
      enableCrossValidation: enableCV,
      kFolds,
      enrichmentTypes: Array.from(enrichments) as EnrichmentAnalysisType[],
      name: name || "Multi-step experiment",
      enableTreeOptimization: treeOpt.enabled,
      treeOptimizationBudget: treeOpt.enabled ? treeOpt.budget : undefined,
      optimizeOperators: treeOpt.optimizeOperators,
      optimizeOrthologs: treeOpt.optimizeOrthologs,
      optimizeStructure: treeOpt.optimizeStructure,
      optimizationObjective: treeOpt.enabled ? treeOpt.objective : undefined,
    };

    runExperiment(config);
  }, [
    canRun,
    stepTree,
    strategy?.rootStepId,
    steps,
    siteId,
    selectedRecordType,
    positiveControls,
    negativeControls,
    enableCV,
    kFolds,
    enrichments,
    name,
    treeOpt,
    runExperiment,
    clearError,
  ]);

  const goBack = useCallback(() => {
    setView("mode-select");
  }, [setView]);

  const selectedStep = selectedStepId ? (stepsById[selectedStepId] ?? null) : null;

  const warnings = useMemo(() => {
    const w: { stepId: string; message: string; severity: "warning" | "error" }[] = [];
    for (const step of steps) {
      if (step.resultCount === 0) {
        w.push({
          stepId: step.id,
          message: `"${step.displayName}" returns 0 results`,
          severity: "error",
        });
      } else if (typeof step.resultCount === "number" && step.resultCount > 50000) {
        w.push({
          stepId: step.id,
          message: `"${step.displayName}" returns ${step.resultCount.toLocaleString()} results — very broad`,
          severity: "warning",
        });
      }
    }
    return w;
  }, [steps]);

  return {
    stepsById,
    steps,
    strategy,
    planResult,
    selectedRecordType,
    recordTypes,
    searches: filteredSearches,
    searchFilter,
    setSearchFilter,

    positiveGenes,
    setPositiveGenes,
    negativeGenes,
    setNegativeGenes,
    positiveControls,
    negativeControls,
    showGeneLookup,
    setShowGeneLookup,

    name,
    setName,
    enableCV,
    setEnableCV,
    kFolds,
    kFoldsDraft,
    setKFolds,
    setKFoldsDraft,
    enrichments,
    toggleEnrichment,
    treeOpt,
    setTreeOpt,

    selectedStepId,
    setSelectedStepId,
    selectedStep,
    importModalOpen,
    setImportModalOpen,

    warnings,
    canRun,
    isRunning,
    storeError,

    addSearchStep,
    addCombineStep,
    updateStep,
    removeStep,
    loadImportedSteps,
    handleRecordTypeChange,
    handleRun,
    refreshCounts,
    goBack,
  };
}
