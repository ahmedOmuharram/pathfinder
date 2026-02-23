import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  EnrichmentAnalysisType,
  ParamSpec,
  RecordType,
  Search,
} from "@pathfinder/shared";
import { useExperimentStore } from "../../store";
import { getRecordTypes, getSearches, getParamSpecs } from "@/lib/api/client";
import { isParamRequired, isParamEmpty } from "../paramUtils";
import type { WizardStep as AiWizardStep } from "../../api";
import type { SearchSuggestion, RunConfigSuggestion } from "../../suggestionParser";
import { GENE_RECORD_TYPES } from "./constants";
import { buildExperimentConfig } from "./buildExperimentConfig";
import { computeStepValidation } from "./stepValidation";
import { buildInitialParamsFromSpecs } from "./paramInitialState";
import { applyCloneConfig } from "./applyCloneConfig";

export function useSetupWizard(siteId: string) {
  const {
    runExperiment,
    setView,
    isRunning,
    error: storeError,
    clearError,
    cloneConfig,
    clearClone,
  } = useExperimentStore();

  const [step, setStep] = useState(0);
  const [attemptedSteps, setAttemptedSteps] = useState<Set<number>>(new Set());

  const [allRecordTypes, setAllRecordTypes] = useState<RecordType[]>([]);
  const [searches, setSearches] = useState<Search[]>([]);
  const [selectedRecordType, setSelectedRecordType] = useState("gene");
  const [selectedSearch, setSelectedSearch] = useState("");
  const [searchFilter, setSearchFilter] = useState("");

  const recordTypes = useMemo(
    () => allRecordTypes.filter((rt) => GENE_RECORD_TYPES.has(rt.name)),
    [allRecordTypes],
  );

  const [paramSpecs, setParamSpecs] = useState<ParamSpec[]>([]);
  const [paramSpecsLoading, setParamSpecsLoading] = useState(false);
  const [parameters, setParameters] = useState<Record<string, string>>({});

  const [positiveGenes, setPositiveGenes] = useState<{ geneId: string }[]>([]);
  const [negativeGenes, setNegativeGenes] = useState<{ geneId: string }[]>([]);
  const controlsSearchName = "GeneByLocusTag";
  const controlsParamName = "ds_gene_ids";
  const [showGeneLookup, setShowGeneLookup] = useState(false);

  const AI_STEP_MAP: AiWizardStep[] = ["search", "parameters", "controls", "run"];
  const currentAiStep = AI_STEP_MAP[step];

  const [name, setName] = useState("");
  const [enableCV, setEnableCV] = useState(false);
  const [kFolds, setKFolds] = useState(5);
  const [kFoldsDraft, setKFoldsDraft] = useState("5");
  const [enrichments, setEnrichments] = useState<Set<EnrichmentAnalysisType>>(
    new Set(),
  );

  const pendingCloneParams = useRef<Record<string, unknown> | null>(null);
  const pendingSuggestedParams = useRef<Record<string, string> | null>(null);

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
    clearClone();
  }, [cloneConfig, clearClone]);

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
      })
      .catch(() => setParamSpecs([]))
      .finally(() => setParamSpecsLoading(false));
  }, [siteId, selectedRecordType, selectedSearch]);

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

  const isTransformSearch = useMemo(
    () => paramSpecs.some((s) => s.type === "input-step"),
    [paramSpecs],
  );

  const visibleParamSpecs = useMemo(
    () => paramSpecs.filter((s) => s.type !== "input-step"),
    [paramSpecs],
  );

  const aiContext = useMemo(
    () => ({
      recordType: selectedRecordType,
      searchName: selectedSearch,
      parameters,
      positiveControls,
      negativeControls,
    }),
    [
      selectedRecordType,
      selectedSearch,
      parameters,
      positiveControls,
      negativeControls,
    ],
  );

  const emptyRequiredParams = useMemo(
    () =>
      visibleParamSpecs.filter(
        (spec) =>
          isParamRequired(spec) && isParamEmpty(spec, parameters[spec.name] ?? ""),
      ),
    [visibleParamSpecs, parameters],
  );

  const stepValidation = useMemo(
    () =>
      computeStepValidation({
        step,
        selectedSearch,
        paramSpecsLoading,
        emptyRequiredParams,
        positiveControls,
        negativeControls,
      }),
    [
      step,
      selectedSearch,
      paramSpecsLoading,
      emptyRequiredParams,
      positiveControls,
      negativeControls,
    ],
  );

  const canNext = useCallback(() => stepValidation.valid, [stepValidation]);

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
    const gene = { geneId };
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

  const handleRun = useCallback(() => {
    clearError();
    const config = buildExperimentConfig({
      siteId,
      selectedRecordType,
      selectedSearch,
      parameters,
      paramSpecs,
      positiveControls,
      negativeControls,
      enableCV,
      kFolds,
      enrichments,
      name,
      controlsSearchName,
      controlsParamName,
    });
    runExperiment(config);
  }, [
    siteId,
    selectedRecordType,
    selectedSearch,
    parameters,
    paramSpecs,
    positiveControls,
    negativeControls,
    enableCV,
    kFolds,
    enrichments,
    name,
    runExperiment,
    clearError,
  ]);

  const goBack = useCallback(() => {
    if (step === 0) setView("list");
    else setStep((s) => s - 1);
  }, [step, setView]);

  const goNext = useCallback(() => {
    setAttemptedSteps((prev) => new Set(prev).add(step));
    if (canNext()) setStep((s) => s + 1);
  }, [step, canNext]);

  const runOrValidate = useCallback(() => {
    setAttemptedSteps((prev) => new Set(prev).add(step));
    if (canNext() && !isRunning) handleRun();
  }, [step, canNext, isRunning, handleRun]);

  return {
    step,
    setStep,
    attemptedSteps,
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
    visibleParamSpecs,
    positiveGenes,
    setPositiveGenes,
    negativeGenes,
    setNegativeGenes,
    showGeneLookup,
    setShowGeneLookup,
    currentAiStep,
    aiContext,
    name,
    setName,
    enableCV,
    setEnableCV,
    kFolds,
    kFoldsDraft,
    setKFolds,
    setKFoldsDraft,
    enrichments,
    positiveControls,
    negativeControls,
    isTransformSearch,
    stepValidation,
    storeError,
    isRunning,
    handleRecordTypeChange,
    handleSuggestionApply,
    handleGeneAdd,
    handleParamsApply,
    handleRunConfigApply,
    handleParameterChange,
    toggleEnrichment,
    goBack,
    goNext,
    runOrValidate,
    canNext,
  };
}
