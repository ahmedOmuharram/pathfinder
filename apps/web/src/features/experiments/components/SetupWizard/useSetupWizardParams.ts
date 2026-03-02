import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  EnrichmentAnalysisType,
  OptimizeSpec,
  ParamSpec,
  RecordType,
  ResolvedGene,
  Search,
} from "@pathfinder/shared";
import { useExperimentViewStore } from "../../store";
import { getRecordTypes, getSearches, getParamSpecs } from "@/lib/api/client";
import { buildAutoOptimizeSpecs } from "../paramUtils";
import type { SearchSuggestion, RunConfigSuggestion } from "../../suggestionParser";
import { GENE_RECORD_TYPES } from "./constants";
import { buildInitialParamsFromSpecs } from "./paramInitialState";
import { applyCloneConfig } from "./applyCloneConfig";

export function useSetupWizardParams(siteId: string) {
  const { cloneConfig, cloneWithOptimize, clearClone } = useExperimentViewStore();

  // --------------- Record types & searches ---------------
  const [allRecordTypes, setAllRecordTypes] = useState<RecordType[]>([]);
  const [searches, setSearches] = useState<Search[]>([]);
  const [selectedRecordType, setSelectedRecordType] = useState("gene");
  const [selectedSearch, setSelectedSearch] = useState("");
  const [searchFilter, setSearchFilter] = useState("");

  const recordTypes = useMemo(
    () => allRecordTypes.filter((rt) => GENE_RECORD_TYPES.has(rt.name)),
    [allRecordTypes],
  );

  // --------------- Param specs & values ---------------
  const [paramSpecs, setParamSpecs] = useState<ParamSpec[]>([]);
  const [paramSpecsLoading, setParamSpecsLoading] = useState(false);
  const [parameters, setParameters] = useState<Record<string, string>>({});

  // --------------- Gene controls ---------------
  const [positiveGenes, setPositiveGenes] = useState<ResolvedGene[]>([]);
  const [negativeGenes, setNegativeGenes] = useState<ResolvedGene[]>([]);
  const [showGeneLookup, setShowGeneLookup] = useState(false);

  // --------------- Run config ---------------
  const [name, setName] = useState("");
  const [enableCV, setEnableCV] = useState(false);
  const [kFolds, setKFolds] = useState(5);
  const [kFoldsDraft, setKFoldsDraft] = useState("5");
  const [enrichments, setEnrichments] = useState<Set<EnrichmentAnalysisType>>(
    new Set(),
  );

  // --------------- Optimization ---------------
  const [optimizeSpecs, setOptimizeSpecs] = useState<Map<string, OptimizeSpec>>(
    new Map(),
  );
  const [optimizationBudget, setOptimizationBudget] = useState(30);
  const [optimizationBudgetDraft, setOptimizationBudgetDraft] = useState("30");
  const [optimizationObjective, setOptimizationObjective] =
    useState<string>("balanced_accuracy");

  // --------------- Batch mode ---------------
  const [batchMode, setBatchMode] = useState(false);
  const [batchOrganisms, setBatchOrganisms] = useState<string[]>([]);
  const [batchOrganismControls, setBatchOrganismControls] = useState<
    Record<string, { positive: string; negative: string }>
  >({});

  const { organismParamName, organismOptions } = useMemo(() => {
    const orgSpec = paramSpecs.find(
      (s) => s.name === "organism" || s.name === "organisms",
    );
    if (!orgSpec || !orgSpec.vocabulary)
      return { organismParamName: "", organismOptions: [] as string[] };
    const entries = Array.isArray(orgSpec.vocabulary)
      ? orgSpec.vocabulary
      : typeof orgSpec.vocabulary === "object"
        ? Object.entries(orgSpec.vocabulary).map(([k, v]) => ({
            value: String(k),
            display: String(v),
          }))
        : [];
    return {
      organismParamName: orgSpec.name,
      organismOptions: entries.map((e: { value: string }) => e.value),
    };
  }, [paramSpecs]);

  // --------------- Pending refs for clone / suggestion ---------------
  const pendingCloneParams = useRef<Record<string, unknown> | null>(null);
  const pendingSuggestedParams = useRef<Record<string, string> | null>(null);
  const pendingAutoOptimize = useRef(false);

  // --------------- Effects: clone config ---------------
  useEffect(() => {
    if (!cloneConfig) return;
    pendingCloneParams.current = applyCloneConfig(cloneConfig, {
      setSelectedRecordType,
      setSelectedSearch,
      setName,
      setEnableCV,
      setKFolds,
      setKFoldsDraft,
      setEnrichments,
      setPositiveGenes,
      setNegativeGenes,
    });
    if (cloneWithOptimize) {
      pendingAutoOptimize.current = true;
      queueMicrotask(() => {
        if (cloneConfig.optimizationBudget)
          setOptimizationBudget(cloneConfig.optimizationBudget);
        if (cloneConfig.optimizationObjective)
          setOptimizationObjective(cloneConfig.optimizationObjective);
      });
    }
    clearClone();
  }, [cloneConfig, cloneWithOptimize, clearClone]);

  // --------------- Effects: data fetching ---------------
  useEffect(() => {
    getRecordTypes(siteId)
      .then(setAllRecordTypes)
      .catch((err) => console.error("[useSetupWizardParams.loadRecordTypes]", err));
  }, [siteId]);

  useEffect(() => {
    getSearches(siteId, selectedRecordType)
      .then(setSearches)
      .catch((err) => console.error("[useSetupWizardParams.loadSearches]", err));
  }, [siteId, selectedRecordType]);

  useEffect(() => {
    if (!selectedSearch || !selectedRecordType) {
      queueMicrotask(() => setParamSpecs([]));
      return;
    }
    queueMicrotask(() => setParamSpecsLoading(true));
    getParamSpecs(siteId, selectedRecordType, selectedSearch)
      .then((specs) => {
        setParamSpecs(specs);
        const cloned = pendingCloneParams.current;
        pendingCloneParams.current = null;
        const suggested = pendingSuggestedParams.current;
        pendingSuggestedParams.current = null;
        const initial = buildInitialParamsFromSpecs(specs, cloned, suggested);
        setParameters(initial);

        if (pendingAutoOptimize.current) {
          pendingAutoOptimize.current = false;
          const visible = specs.filter((s) => s.type !== "input-step");
          setOptimizeSpecs(buildAutoOptimizeSpecs(visible));
        }
      })
      .catch((err) => {
        console.error("[useSetupWizardParams.loadParamSpecs]", err);
        setParamSpecs([]);
      })
      .finally(() => setParamSpecsLoading(false));
  }, [siteId, selectedRecordType, selectedSearch]);

  // --------------- Derived data ---------------
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

  // --------------- Handlers ---------------
  const handleRecordTypeChange = useCallback((rt: string) => {
    setSelectedRecordType(rt);
    setSelectedSearch("");
  }, []);

  const handleSuggestionApply = useCallback(
    (suggestion: SearchSuggestion) => {
      if (suggestion.recordType && suggestion.recordType !== selectedRecordType) {
        setSelectedRecordType(suggestion.recordType);
      }
      if (suggestion.suggestedParameters) {
        pendingSuggestedParams.current = suggestion.suggestedParameters;
      }
      setSelectedSearch(suggestion.searchName);
    },
    [selectedRecordType],
  );

  const handleGeneAdd = useCallback((geneId: string, role: "positive" | "negative") => {
    const gene: ResolvedGene = {
      geneId,
      displayName: geneId,
      organism: "",
      product: "",
      geneName: "",
      geneType: "",
      location: "",
    };
    if (role === "positive") {
      setPositiveGenes((prev) =>
        prev.some((g) => g.geneId === geneId) ? prev : [...prev, gene],
      );
    } else {
      setNegativeGenes((prev) =>
        prev.some((g) => g.geneId === geneId) ? prev : [...prev, gene],
      );
    }
  }, []);

  const handleParamsApply = useCallback(
    (params: Record<string, string>) =>
      setParameters((prev) => ({ ...prev, ...params })),
    [],
  );

  const handleRunConfigApply = useCallback((config: RunConfigSuggestion) => {
    if (config.name) setName(config.name);
    if (config.enableCrossValidation !== undefined)
      setEnableCV(config.enableCrossValidation);
    if (config.kFolds !== undefined) {
      setKFolds(config.kFolds);
      setKFoldsDraft(String(config.kFolds));
    }
    if (config.enrichmentTypes) {
      setEnrichments(new Set(config.enrichmentTypes as EnrichmentAnalysisType[]));
    }
  }, []);

  const handleParameterChange = useCallback(
    (pName: string, value: string) => setParameters((p) => ({ ...p, [pName]: value })),
    [],
  );

  const toggleEnrichment = useCallback((type: EnrichmentAnalysisType) => {
    setEnrichments((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }, []);

  const handleOptimizeChange = useCallback(
    (paramName: string, spec: OptimizeSpec | null) => {
      setOptimizeSpecs((prev) => {
        const next = new Map(prev);
        if (spec) next.set(paramName, spec);
        else next.delete(paramName);
        return next;
      });
    },
    [],
  );

  return {
    // State
    recordTypes,
    selectedRecordType,
    filteredSearches,
    searchFilter,
    setSearchFilter,
    selectedSearch,
    setSelectedSearch,
    paramSpecs,
    paramSpecsLoading,
    parameters,
    setParameters,
    positiveGenes,
    setPositiveGenes,
    negativeGenes,
    setNegativeGenes,
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
    optimizeSpecs,
    optimizationBudget,
    optimizationBudgetDraft,
    setOptimizationBudget,
    setOptimizationBudgetDraft,
    optimizationObjective,
    setOptimizationObjective,
    batchMode,
    setBatchMode,
    batchOrganisms,
    setBatchOrganisms,
    batchOrganismControls,
    setBatchOrganismControls,
    organismParamName,
    organismOptions,
    // Handlers
    handleRecordTypeChange,
    handleSuggestionApply,
    handleGeneAdd,
    handleParamsApply,
    handleRunConfigApply,
    handleParameterChange,
    handleOptimizeChange,
    toggleEnrichment,
  };
}
