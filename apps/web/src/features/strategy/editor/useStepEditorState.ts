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

  const form = useParamForm(paramState.paramSpecs);

  const getDirtyFields = (): Partial<Record<string, boolean>> => {
    const meta = form.state.fieldMeta;
    const result: Partial<Record<string, boolean>> = {};
    for (const [name, fieldMeta] of Object.entries(meta)) {
      if (fieldMeta?.isDirty === true) {
        result[name] = true;
      }
    }
    return result;
  };

  const setFieldError = (_name: string, _error: { type: string; message: string }) => {
    // Server-side field errors are displayed via the validation.error state
    // in the step editor rather than per-field TanStack Form errors.
    // The save handler already calls setError() with formatted WDK messages.
  };

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

  return {
    kind: metadata.kind,
    stepValidationError: metadata.stepValidationError,

    oldName: metadata.oldName,
    name: metadata.name,
    setName: metadata.setName,

    siteId,
    editableSearchName: searchState.editableSearchName,
    setEditableSearchName: searchState.setEditableSearchName,
    searchName: searchState.searchName,
    selectedSearch: searchState.selectedSearch,
    isSearchNameAvailable: searchState.isSearchNameAvailable,
    searchOptions: searchState.searchOptions,
    filteredSearchOptions: searchState.filteredSearchOptions,

    recordTypeValue: recordTypeState.recordTypeValue,
    setRecordTypeValue: recordTypeState.setRecordTypeValue,
    normalizedRecordTypeValue: recordTypeState.normalizedRecordTypeValue,
    recordTypeFilter: recordTypeState.recordTypeFilter,
    setRecordTypeFilter: recordTypeState.setRecordTypeFilter,
    recordTypeOptions: recordTypeState.recordTypeOptions,
    filteredRecordTypes: recordTypeState.filteredRecordTypes,
    recordType,

    paramSpecs: paramState.paramSpecs,
    parameters: paramState.parameters,
    setParameters: paramState.setParameters,
    vocabOptions: paramState.vocabOptions,
    hiddenDefaults: paramState.hiddenDefaults,
    dependentOptions: paramState.dependentOptions,
    dependentLoading: paramState.dependentLoading,
    dependentErrors: paramState.dependentErrors,
    validationErrorKeys: validation.validationErrorKeys,

    error: validation.error,
    setError: validation.setError,
    isLoading: paramState.isLoading,

    operatorValue: metadata.operatorValue,
    setOperatorValue: metadata.setOperatorValue,
    colocationParams: metadata.colocationParams,
    setColocationParams: metadata.setColocationParams,

    form,

    handleSave,
  };
}

export type StepEditorState = ReturnType<typeof useStepEditorState>;
