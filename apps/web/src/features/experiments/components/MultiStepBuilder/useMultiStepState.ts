import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  EnrichmentAnalysisType,
  OperatorKnob,
  RecordType,
  ResolvedGene,
  Search,
  StepAnalysisPhase,
  ThresholdKnob,
  StrategyStep,
  StrategyWithMeta,
} from "@pathfinder/shared";
import type { StepAnalysisConfig } from "./ConfigPanel";
import { useExperimentViewStore } from "../../store";
import { getRecordTypes, getSearches, computeStepCounts } from "@/lib/api/client";
import { serializeStrategyPlan } from "@/lib/strategyGraph";
import { useStepCounts } from "@/features/strategy/services/useStepCounts";
import { GENE_RECORD_TYPES } from "../SetupWizard/constants";
import {
  buildLocalStrategy,
  DEFAULT_STEP_ANALYSIS,
  applyMultiStepClone,
} from "./multiStepUtils";

export interface MultiStepState {
  /* Step tree */
  stepsById: Record<string, StrategyStep>;
  setStepsById: React.Dispatch<React.SetStateAction<Record<string, StrategyStep>>>;
  steps: StrategyStep[];
  strategy: StrategyWithMeta | null;
  planResult: ReturnType<typeof serializeStrategyPlan> | null;
  planHash: string | null;

  /* Record types & searches */
  allRecordTypes: RecordType[];
  recordTypes: RecordType[];
  searches: Search[];
  filteredSearches: Search[];
  selectedRecordType: string;
  setSelectedRecordType: (v: string) => void;
  searchFilter: string;
  setSearchFilter: (v: string) => void;

  /* Controls */
  positiveGenes: ResolvedGene[];
  setPositiveGenes: React.Dispatch<React.SetStateAction<ResolvedGene[]>>;
  negativeGenes: ResolvedGene[];
  setNegativeGenes: React.Dispatch<React.SetStateAction<ResolvedGene[]>>;
  positiveControls: string[];
  negativeControls: string[];
  showGeneLookup: boolean;
  setShowGeneLookup: (v: boolean) => void;

  /* Experiment configuration */
  name: string;
  setName: (v: string) => void;
  enableCV: boolean;
  setEnableCV: (v: boolean) => void;
  kFolds: number;
  setKFolds: (v: number) => void;
  kFoldsDraft: string;
  setKFoldsDraft: (v: string) => void;
  enrichments: Set<EnrichmentAnalysisType>;
  setEnrichments: React.Dispatch<React.SetStateAction<Set<EnrichmentAnalysisType>>>;
  stepAnalysis: StepAnalysisConfig;
  setStepAnalysis: (v: StepAnalysisConfig) => void;
  thresholdKnobs: ThresholdKnob[];
  setThresholdKnobs: (v: ThresholdKnob[]) => void;
  operatorKnobs: OperatorKnob[];
  setOperatorKnobs: (v: OperatorKnob[]) => void;
  treeOptObjective: string;
  setTreeOptObjective: (v: string) => void;
  sortAttribute: string | null;
  setSortAttribute: (v: string | null) => void;
  sortDirection: "ASC" | "DESC";
  setSortDirection: (v: "ASC" | "DESC") => void;
  sortableAttributes: { name: string; displayName: string; isSuggested?: boolean }[];
  setSortableAttributes: (
    v: { name: string; displayName: string; isSuggested?: boolean }[],
  ) => void;

  /* Benchmark */
  benchmarkMode: boolean;
  setBenchmarkMode: (v: boolean) => void;
  benchmarkControlSets: {
    label: string;
    positiveControls: string[];
    negativeControls: string[];
    controlSetId?: string | null;
    isPrimary: boolean;
  }[];
  setBenchmarkControlSets: (
    v: {
      label: string;
      positiveControls: string[];
      negativeControls: string[];
      controlSetId?: string | null;
      isPrimary: boolean;
    }[],
  ) => void;

  /* Controls constants */
  controlsSearchName: string;
  controlsParamName: string;

  /* Selection & modals */
  selectedStepId: string | null;
  setSelectedStepId: React.Dispatch<React.SetStateAction<string | null>>;
  selectedStep: StrategyStep | null;
  importModalOpen: boolean;
  setImportModalOpen: (v: boolean) => void;

  /* Refresh */
  refreshKey: number;
  setRefreshKey: React.Dispatch<React.SetStateAction<number>>;
}

export function useMultiStepState(siteId: string): MultiStepState {
  const { cloneConfig, cloneWithOptimize, clearClone } = useExperimentViewStore();

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
  const [stepAnalysis, setStepAnalysis] =
    useState<StepAnalysisConfig>(DEFAULT_STEP_ANALYSIS);
  const [thresholdKnobs, setThresholdKnobs] = useState<ThresholdKnob[]>([]);
  const [operatorKnobs, setOperatorKnobs] = useState<OperatorKnob[]>([]);
  const [treeOptObjective, setTreeOptObjective] = useState("precision_at_50");
  const [sortAttribute, setSortAttribute] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<"ASC" | "DESC">("ASC");
  const [sortableAttributes, setSortableAttributes] = useState<
    { name: string; displayName: string; isSuggested?: boolean }[]
  >([]);
  const [benchmarkMode, setBenchmarkMode] = useState(false);
  const [benchmarkControlSets, setBenchmarkControlSets] = useState<
    {
      label: string;
      positiveControls: string[];
      negativeControls: string[];
      controlSetId?: string | null;
      isPrimary: boolean;
    }[]
  >([]);
  const controlsSearchName = "GeneByLocusTag";
  const controlsParamName = "ds_gene_ids";

  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [importModalOpen, setImportModalOpen] = useState(false);

  /* ── Derived values ─────────────────────────────────────────────── */

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

  const selectedStep = selectedStepId ? (stepsById[selectedStepId] ?? null) : null;

  /* ── Step counts ────────────────────────────────────────────────── */

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

  /* ── Data fetching ──────────────────────────────────────────────── */

  useEffect(() => {
    getRecordTypes(siteId)
      .then(setAllRecordTypes)
      .catch((err) => console.error("[useMultiStepState.loadRecordTypes]", err));
  }, [siteId]);

  useEffect(() => {
    getSearches(siteId, selectedRecordType)
      .then(setSearches)
      .catch((err) => console.error("[useMultiStepState.loadSearches]", err));
  }, [siteId, selectedRecordType]);

  /* ── Clone hydration ────────────────────────────────────────────── */

  const loadImportedStepsForClone = useCallback(
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
        loadImportedSteps: loadImportedStepsForClone,
        setStepAnalysis,
      },
      cloneWithOptimize,
    );
    clearClone();
  }, [cloneConfig, cloneWithOptimize, clearClone, loadImportedStepsForClone]);

  return {
    stepsById,
    setStepsById,
    steps,
    strategy,
    planResult,
    planHash,

    allRecordTypes,
    recordTypes,
    searches,
    filteredSearches,
    selectedRecordType,
    setSelectedRecordType,
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
    setKFolds,
    kFoldsDraft,
    setKFoldsDraft,
    enrichments,
    setEnrichments,
    stepAnalysis,
    setStepAnalysis,
    thresholdKnobs,
    setThresholdKnobs,
    operatorKnobs,
    setOperatorKnobs,
    treeOptObjective,
    setTreeOptObjective,
    sortAttribute,
    setSortAttribute,
    sortDirection,
    setSortDirection,
    sortableAttributes,
    setSortableAttributes,

    benchmarkMode,
    setBenchmarkMode,
    benchmarkControlSets,
    setBenchmarkControlSets,

    controlsSearchName,
    controlsParamName,

    selectedStepId,
    setSelectedStepId,
    selectedStep,
    importModalOpen,
    setImportModalOpen,

    refreshKey,
    setRefreshKey,
  };
}
