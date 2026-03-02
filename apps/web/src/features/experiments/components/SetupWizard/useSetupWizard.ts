import { useCallback } from "react";
import { useExperimentRunStore } from "../../store";
import { useSetupWizardParams } from "./useSetupWizardParams";
import { useSetupWizardValidation } from "./useSetupWizardValidation";
import { useSetupWizardNavigation } from "./useSetupWizardNavigation";
import { buildExperimentConfig } from "./buildExperimentConfig";

const controlsSearchName = "GeneByLocusTag";
const controlsParamName = "ds_gene_ids";

export function useSetupWizard(siteId: string) {
  const {
    runExperiment,
    runBatchExperiment,
    isRunning,
    error: storeError,
    clearError,
  } = useExperimentRunStore();

  const nav = useSetupWizardNavigation();
  const params = useSetupWizardParams(siteId);

  const validation = useSetupWizardValidation({
    step: nav.step,
    selectedSearch: params.selectedSearch,
    selectedRecordType: params.selectedRecordType,
    paramSpecs: params.paramSpecs,
    paramSpecsLoading: params.paramSpecsLoading,
    parameters: params.parameters,
    positiveGenes: params.positiveGenes,
    negativeGenes: params.negativeGenes,
  });

  // --- Bridge: canNext, goNext, runOrValidate depend on both nav and validation ---

  const canNext = useCallback(
    () => validation.stepValidation.valid,
    [validation.stepValidation],
  );

  const goNext = useCallback(() => {
    nav.markStepAttempted();
    if (validation.stepValidation.valid) nav.advanceStep();
  }, [nav, validation.stepValidation]);

  const handleRun = useCallback(() => {
    clearError();
    const config = buildExperimentConfig({
      siteId,
      selectedRecordType: params.selectedRecordType,
      selectedSearch: params.selectedSearch,
      parameters: params.parameters,
      paramSpecs: params.paramSpecs,
      positiveControls: validation.positiveControls,
      negativeControls: validation.negativeControls,
      enableCV: params.enableCV,
      kFolds: params.kFolds,
      enrichments: params.enrichments,
      name: params.name,
      controlsSearchName,
      controlsParamName,
      optimizeSpecs: params.optimizeSpecs,
      optimizationBudget: params.optimizationBudget,
      optimizationObjective: params.optimizationObjective,
    });

    if (
      params.batchMode &&
      params.batchOrganisms.length > 0 &&
      params.organismParamName
    ) {
      const targets = params.batchOrganisms.map((org) => {
        const overrides = params.batchOrganismControls[org];
        const orgPos = overrides?.positive.trim()
          ? overrides.positive
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          : validation.positiveControls;
        const orgNeg = overrides?.negative.trim()
          ? overrides.negative
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          : validation.negativeControls;
        return {
          organism: org,
          positiveControls: orgPos,
          negativeControls: orgNeg,
        };
      });
      runBatchExperiment(config, params.organismParamName, targets);
    } else {
      runExperiment(config);
    }
  }, [
    siteId,
    params.selectedRecordType,
    params.selectedSearch,
    params.parameters,
    params.paramSpecs,
    validation.positiveControls,
    validation.negativeControls,
    params.enableCV,
    params.kFolds,
    params.enrichments,
    params.name,
    params.optimizeSpecs,
    params.optimizationBudget,
    params.optimizationObjective,
    params.batchMode,
    params.batchOrganisms,
    params.batchOrganismControls,
    params.organismParamName,
    runExperiment,
    runBatchExperiment,
    clearError,
  ]);

  const runOrValidate = useCallback(() => {
    nav.markStepAttempted();
    if (validation.stepValidation.valid && !isRunning) handleRun();
  }, [nav, validation.stepValidation, isRunning, handleRun]);

  return {
    // Navigation
    step: nav.step,
    setStep: nav.setStep,
    attemptedSteps: nav.attemptedSteps,
    currentAiStep: nav.currentAiStep,
    goBack: nav.goBack,
    goNext,
    canNext,
    runOrValidate,
    isRunning,
    storeError,

    // Params / state
    recordTypes: params.recordTypes,
    selectedRecordType: params.selectedRecordType,
    filteredSearches: params.filteredSearches,
    searchFilter: params.searchFilter,
    setSearchFilter: params.setSearchFilter,
    selectedSearch: params.selectedSearch,
    setSelectedSearch: params.setSelectedSearch,
    paramSpecs: params.paramSpecs,
    paramSpecsLoading: params.paramSpecsLoading,
    parameters: params.parameters,
    setParameters: params.setParameters,
    positiveGenes: params.positiveGenes,
    setPositiveGenes: params.setPositiveGenes,
    negativeGenes: params.negativeGenes,
    setNegativeGenes: params.setNegativeGenes,
    showGeneLookup: params.showGeneLookup,
    setShowGeneLookup: params.setShowGeneLookup,
    name: params.name,
    setName: params.setName,
    enableCV: params.enableCV,
    setEnableCV: params.setEnableCV,
    kFolds: params.kFolds,
    kFoldsDraft: params.kFoldsDraft,
    setKFolds: params.setKFolds,
    setKFoldsDraft: params.setKFoldsDraft,
    enrichments: params.enrichments,
    optimizeSpecs: params.optimizeSpecs,
    optimizationBudget: params.optimizationBudget,
    optimizationBudgetDraft: params.optimizationBudgetDraft,
    setOptimizationBudget: params.setOptimizationBudget,
    setOptimizationBudgetDraft: params.setOptimizationBudgetDraft,
    optimizationObjective: params.optimizationObjective,
    setOptimizationObjective: params.setOptimizationObjective,
    batchMode: params.batchMode,
    setBatchMode: params.setBatchMode,
    batchOrganisms: params.batchOrganisms,
    setBatchOrganisms: params.setBatchOrganisms,
    batchOrganismControls: params.batchOrganismControls,
    setBatchOrganismControls: params.setBatchOrganismControls,
    organismParamName: params.organismParamName,
    organismOptions: params.organismOptions,

    // Handlers
    handleRecordTypeChange: params.handleRecordTypeChange,
    handleSuggestionApply: params.handleSuggestionApply,
    handleGeneAdd: params.handleGeneAdd,
    handleParamsApply: params.handleParamsApply,
    handleRunConfigApply: params.handleRunConfigApply,
    handleParameterChange: params.handleParameterChange,
    handleOptimizeChange: params.handleOptimizeChange,
    toggleEnrichment: params.toggleEnrichment,

    // Validation / derived
    visibleParamSpecs: validation.visibleParamSpecs,
    positiveControls: validation.positiveControls,
    negativeControls: validation.negativeControls,
    isTransformSearch: validation.isTransformSearch,
    stepValidation: validation.stepValidation,
    aiContext: validation.aiContext,
  };
}
