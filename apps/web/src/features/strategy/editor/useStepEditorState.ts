"use client";

import { useCallback, useEffect, useRef, startTransition } from "react";
import type { UseFormReturn } from "react-hook-form";
import { usePrevious } from "@/lib/hooks/usePrevious";
import type { Step } from "@pathfinder/shared";
import { coerceParametersForSpecs } from "@/features/strategy/parameters/coerce";
import { normalizeRecordType } from "@/lib/utils/normalizeRecordType";
import { useStepMetadata } from "./hooks/useStepMetadata";
import { useStepRecordType } from "./hooks/useStepRecordType";
import { useStepSearch } from "./hooks/useStepSearch";
import { useStepParameters } from "./hooks/useStepParameters";
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
    stepId: step.id,
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
  // RHF form instance — exposed from StepParamFields via onFormReady callback.
  // We store the form in a ref so it is never stale and so reading it doesn't
  // trigger re-renders. The getDirtyFields / setFieldError callbacks read
  // the ref lazily at invocation time (event handler scope, not render scope).
  // ---------------------------------------------------------------------------
  const formRef = useRef<UseFormReturn | null>(null);
  const onFormReady = useCallback((form: UseFormReturn) => {
    formRef.current = form;
  }, []);

  const getDirtyFields = useCallback((): Partial<Record<string, boolean>> => {
    const fields = formRef.current?.formState.dirtyFields;
    return (fields ?? {}) as Partial<Record<string, boolean>>;
  }, []);

  const setFieldError = useCallback(
    (name: string, error: { type: string; message: string }) => {
      formRef.current?.setError(name, error);
    },
    [],
  );

  // ---------------------------------------------------------------------------
  // Sync form state when a different step is selected
  // ---------------------------------------------------------------------------
  const prevStepId = usePrevious(step.id);

  useEffect(() => {
    const isNewStep = prevStepId !== step.id;
    if (!isNewStep) return;
    if (paramState.isLoading) return; // Wait for param specs to load for the new step.

    const nextParams = coerceParametersForSpecs(
      step.parameters ?? {},
      paramState.paramSpecs,
      // Normal UI flow: do not accept/parse stringified arrays or CSV.
      { allowStringParsing: false },
    );
    const nextOldName = step.displayName;
    const nextName = nextOldName;
    const nextSearchName = step.searchName ?? "";
    const nextRecordType = normalizeRecordType(step.recordType ?? recordType);
    // Batch state updates to avoid cascading renders
    startTransition(() => {
      metadata.setOldName(nextOldName);
      metadata.setName(nextName);
      searchState.setEditableSearchName(nextSearchName);
      metadata.setOperatorValue(step.operator ?? "");
      metadata.setColocationParams(step.colocationParams);
      recordTypeState.setRecordTypeValue(nextRecordType);
      paramState.setParameters(nextParams);
    });
  }, [
    prevStepId,
    paramState.isLoading,
    paramState.paramSpecs,
    recordType,
    step.colocationParams,
    step.displayName,
    step.id,
    step.operator,
    step.parameters,
    step.recordType,
    step.searchName,
    metadata,
    searchState,
    recordTypeState,
    paramState,
  ]);

  // ---------------------------------------------------------------------------
  // Save handler (extracted concern).
  // Built lazily at invocation time (not during render) so that
  // getDirtyFields/setFieldError can safely read from the formRef.
  // ---------------------------------------------------------------------------
  const handleSave = useCallback(
    async () => {
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
    },
    [
      step,
      siteId,
      metadata.name,
      metadata.oldName,
      metadata.kind,
      metadata.operatorValue,
      metadata.colocationParams,
      searchState.searchName,
      searchState.selectedSearch,
      searchState.isSearchNameAvailable,
      paramState.parameters,
      paramState.paramSpecs,
      paramState.hiddenDefaults,
      getDirtyFields,
      recordTypeState.recordTypeValue,
      recordTypeState.resolveRecordTypeForSearch,
      onUpdate,
      onClose,
      validation.setError,
      setFieldError,
    ],
  );

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
    isLoadingSearches: searchState.isLoadingSearches,
    searchListError: searchState.searchListError,

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
    onFormReady,

    // Actions
    handleSave,
  };
}

export type StepEditorState = ReturnType<typeof useStepEditorState>;
