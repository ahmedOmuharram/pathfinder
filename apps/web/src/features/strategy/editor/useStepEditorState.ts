"use client";

import type { Step } from "@pathfinder/shared";
import { useStepMetadata } from "./hooks/useStepMetadata";
import { useStepRecordType } from "./hooks/useStepRecordType";
import { useStepSearch } from "./hooks/useStepSearch";
import { useStepParameters } from "./hooks/useStepParameters";
import { useParamForm } from "./hooks/useParamForm";
import { useStepValidation } from "./hooks/useStepValidation";
import { buildStepSaveHandler } from "./useStepSaveHandler";

interface UseStepEditorStateArgs {
  step: Step;
  siteId: string;
  recordType: string | null;
  onUpdate: (updates: Partial<Step>) => void;
  onClose: () => void;
}

export function useStepEditorState({
  step,
  siteId,
  recordType,
  onUpdate,
  onClose,
}: UseStepEditorStateArgs) {
  // ---------------------------------------------------------------------------
  // Sub-hooks
  // ---------------------------------------------------------------------------
  const metadata = useStepMetadata({ step });

  const recordTypeState = useStepRecordType({
    siteId,
    recordType,
    initialRecordType: step.recordType ?? recordType,
  });

  const searchState = useStepSearch({
    siteId,
    recordType,
    initialSearchName: step.searchName ?? "",
    resolveRecordTypeForSearch: recordTypeState.resolveRecordTypeForSearch,
  });

  const paramState = useStepParameters({
    siteId,
    recordType,
    kind: metadata.kind,
    searchName: searchState.searchName,
    selectedSearch: searchState.selectedSearch,
    isSearchNameAvailable: searchState.isSearchNameAvailable,
    apiRecordTypeValue: recordTypeState.apiRecordTypeValue,
    resolveRecordTypeForSearch: recordTypeState.resolveRecordTypeForSearch,
    initialParameters: step.parameters ?? {},
  });

  const validation = useStepValidation({
    stepValidationError: metadata.stepValidationError,
    paramSpecs: paramState.paramSpecs,
  });

  // ---------------------------------------------------------------------------
  // RHF form instance — owned here, passed to StepParamFields as prop.
  // ---------------------------------------------------------------------------
  const form = useParamForm(paramState.paramSpecs);

  const getDirtyFields = (): Partial<Record<string, boolean>> => {
    const fields = form.formState.dirtyFields;
    return fields as Partial<Record<string, boolean>>;
  };

  const setFieldError = (name: string, error: { type: string; message: string }) => {
    form.setError(name, error);
  };


  // ---------------------------------------------------------------------------
  // Save handler (extracted concern).
  // Built lazily at invocation time (not during render) so that
  // getDirtyFields/setFieldError can safely read from the formRef.
  // ---------------------------------------------------------------------------
  const handleSave = async () => {
    const handler = buildStepSaveHandler({
      step,
      siteId,
      name: metadata.name ?? "",
      oldName: metadata.oldName ?? "",
      searchName: searchState.searchName,
      selectedSearch: searchState.selectedSearch,
      isSearchNameAvailable: searchState.isSearchNameAvailable,
      kind: metadata.kind,
      parameters: paramState.parameters,
      paramSpecs: paramState.paramSpecs,
      hiddenDefaults: paramState.hiddenDefaults,
      getDirtyFields,
      recordTypeValue: recordTypeState.recordTypeValue,
      resolveRecordTypeForSearch: recordTypeState.resolveRecordTypeForSearch,
      operatorValue: metadata.operatorValue,
      colocationParams: metadata.colocationParams,
      onUpdate,
      onClose,
      setError: validation.setError,
      setFieldError,
    });
    await handler();
  };

  // ---------------------------------------------------------------------------
  // Public surface -- same shape as before for consumers
  // ---------------------------------------------------------------------------
  return {
    // Step metadata
    kind: metadata.kind,
    stepValidationError: metadata.stepValidationError,

    // Name fields
    oldName: metadata.oldName,
    name: metadata.name,
    setName: metadata.setName,

    // Search selector
    siteId,
    editableSearchName: searchState.editableSearchName,
    setEditableSearchName: searchState.setEditableSearchName,
    searchName: searchState.searchName,
    selectedSearch: searchState.selectedSearch,
    isSearchNameAvailable: searchState.isSearchNameAvailable,
    searchOptions: searchState.searchOptions,
    filteredSearchOptions: searchState.filteredSearchOptions,
    // Record type
    recordTypeValue: recordTypeState.recordTypeValue,
    setRecordTypeValue: recordTypeState.setRecordTypeValue,
    normalizedRecordTypeValue: recordTypeState.normalizedRecordTypeValue,
    recordTypeFilter: recordTypeState.recordTypeFilter,
    setRecordTypeFilter: recordTypeState.setRecordTypeFilter,
    recordTypeOptions: recordTypeState.recordTypeOptions,
    filteredRecordTypes: recordTypeState.filteredRecordTypes,
    recordType,

    // Parameters
    paramSpecs: paramState.paramSpecs,
    parameters: paramState.parameters,
    setParameters: paramState.setParameters,
    vocabOptions: paramState.vocabOptions,
    hiddenDefaults: paramState.hiddenDefaults,
    dependentOptions: paramState.dependentOptions,
    dependentLoading: paramState.dependentLoading,
    dependentErrors: paramState.dependentErrors,
    validationErrorKeys: validation.validationErrorKeys,

    // Validation / loading
    error: validation.error,
    setError: validation.setError,
    isLoading: paramState.isLoading,

    // Combine operator
    operatorValue: metadata.operatorValue,
    setOperatorValue: metadata.setOperatorValue,
    colocationParams: metadata.colocationParams,
    setColocationParams: metadata.setColocationParams,

    // Form integration
    form,

    // Actions
    handleSave,
  };
}

export type StepEditorState = ReturnType<typeof useStepEditorState>;
