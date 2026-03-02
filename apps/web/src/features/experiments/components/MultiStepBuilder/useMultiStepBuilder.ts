import { useExperimentRunStore } from "../../store";
import { useMultiStepState } from "./useMultiStepState";
import { useMultiStepActions } from "./useMultiStepActions";
import { useMultiStepValidation } from "./useMultiStepValidation";

export function useMultiStepBuilder(siteId: string) {
  const { isRunning, error: storeError } = useExperimentRunStore();

  const state = useMultiStepState(siteId);
  const { canRun, warnings, stepTree } = useMultiStepValidation(state);
  const actions = useMultiStepActions(siteId, state, canRun, stepTree);

  return {
    /* Step tree */
    stepsById: state.stepsById,
    steps: state.steps,
    strategy: state.strategy,
    planResult: state.planResult,
    selectedRecordType: state.selectedRecordType,
    recordTypes: state.recordTypes,
    searches: state.filteredSearches,
    searchFilter: state.searchFilter,
    setSearchFilter: state.setSearchFilter,

    /* Controls */
    positiveGenes: state.positiveGenes,
    setPositiveGenes: state.setPositiveGenes,
    negativeGenes: state.negativeGenes,
    setNegativeGenes: state.setNegativeGenes,
    positiveControls: state.positiveControls,
    negativeControls: state.negativeControls,
    showGeneLookup: state.showGeneLookup,
    setShowGeneLookup: state.setShowGeneLookup,

    /* Configuration */
    name: state.name,
    setName: state.setName,
    enableCV: state.enableCV,
    setEnableCV: state.setEnableCV,
    kFolds: state.kFolds,
    kFoldsDraft: state.kFoldsDraft,
    setKFolds: state.setKFolds,
    setKFoldsDraft: state.setKFoldsDraft,
    enrichments: state.enrichments,
    toggleEnrichment: actions.toggleEnrichment,
    stepAnalysis: state.stepAnalysis,
    setStepAnalysis: state.setStepAnalysis,
    thresholdKnobs: state.thresholdKnobs,
    setThresholdKnobs: state.setThresholdKnobs,
    operatorKnobs: state.operatorKnobs,
    setOperatorKnobs: state.setOperatorKnobs,
    treeOptObjective: state.treeOptObjective,
    setTreeOptObjective: state.setTreeOptObjective,
    sortAttribute: state.sortAttribute,
    setSortAttribute: state.setSortAttribute,
    sortDirection: state.sortDirection,
    setSortDirection: state.setSortDirection,
    sortableAttributes: state.sortableAttributes,
    setSortableAttributes: state.setSortableAttributes,

    /* Benchmark */
    benchmarkMode: state.benchmarkMode,
    setBenchmarkMode: state.setBenchmarkMode,
    benchmarkControlSets: state.benchmarkControlSets,
    setBenchmarkControlSets: state.setBenchmarkControlSets,

    /* Selection & modals */
    selectedStepId: state.selectedStepId,
    setSelectedStepId: state.setSelectedStepId,
    selectedStep: state.selectedStep,
    importModalOpen: state.importModalOpen,
    setImportModalOpen: state.setImportModalOpen,

    /* Validation */
    warnings,
    canRun,
    isRunning,
    storeError,

    /* Actions */
    addSearchStep: actions.addSearchStep,
    addCombineStep: actions.addCombineStep,
    updateStep: actions.updateStep,
    removeStep: actions.removeStep,
    loadImportedSteps: actions.loadImportedSteps,
    handleRecordTypeChange: actions.handleRecordTypeChange,
    handleRun: actions.handleRun,
    refreshCounts: actions.refreshCounts,
    goBack: actions.goBack,
  };
}
