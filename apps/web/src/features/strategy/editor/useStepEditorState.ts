"use client";

import { useEffect, startTransition } from "react";
import { usePrevious } from "@/lib/hooks/usePrevious";
import type { Step, SearchValidationResponse } from "@pathfinder/shared";
import { validateSearchParams } from "@/lib/api/sites";
import { coerceParametersForSpecs } from "@/features/strategy/parameters/coerce";
import { normalizeRecordType } from "@/lib/utils/normalizeRecordType";
import { formatSearchValidationResponse } from "@/features/strategy/validation/format";
import { toUserMessage } from "@/lib/api/errors";
import { useStepMetadata } from "./hooks/useStepMetadata";
import { useStepRecordType } from "./hooks/useStepRecordType";
import { useStepSearch } from "./hooks/useStepSearch";
import { useStepParameters } from "./hooks/useStepParameters";
import { useStepValidation } from "./hooks/useStepValidation";

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
    initialRecordType: step.recordType || recordType,
  });

  const searchState = useStepSearch({
    siteId,
    recordType,
    initialSearchName: step.searchName || "",
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
    initialParameters: step.parameters || {},
  });

  const validation = useStepValidation({
    stepValidationError: metadata.stepValidationError,
    paramSpecs: paramState.paramSpecs,
  });

  // ---------------------------------------------------------------------------
  // Sync form state when a different step is selected
  // ---------------------------------------------------------------------------
  const prevStepId = usePrevious(step.id);

  useEffect(() => {
    const isNewStep = prevStepId !== step.id;
    if (!isNewStep) return;
    if (paramState.isLoading) return; // Wait for param specs to load for the new step.

    const nextParams = coerceParametersForSpecs(
      step.parameters || {},
      paramState.paramSpecs,
      // Normal UI flow: do not accept/parse stringified arrays or CSV.
      { allowStringParsing: false },
    );
    const nextOldName = step.displayName;
    const nextName = nextOldName;
    const nextSearchName = step.searchName || "";
    const nextRecordType = normalizeRecordType(step.recordType || recordType);
    const nextRawParams = JSON.stringify(nextParams, null, 2);
    // Batch state updates to avoid cascading renders
    startTransition(() => {
      metadata.setOldName(nextOldName);
      metadata.setName(nextName);
      searchState.setEditableSearchName(nextSearchName);
      metadata.setOperatorValue(step.operator || "");
      metadata.setColocationParams(step.colocationParams);
      recordTypeState.setRecordTypeValue(nextRecordType);
      paramState.setParameters(nextParams);
      paramState.setRawParams(nextRawParams);
      paramState.setShowRaw(false);
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
  // Save handler
  // ---------------------------------------------------------------------------
  const handleSave = async () => {
    try {
      const nextName = (metadata.name || "").trim() || metadata.oldName;
      const nextSearchName = searchState.searchName || step.searchName || "";
      let parsedParams = paramState.parameters;
      if (paramState.showRaw) {
        parsedParams = JSON.parse(paramState.rawParams);
      }
      parsedParams = coerceParametersForSpecs(
        parsedParams,
        paramState.paramSpecs,
        // Normal save path: do not accept stringified arrays/CSV.
        { allowStringParsing: false },
      );
      // Merge hidden param defaults (lowest priority — user edits win).
      parsedParams = { ...paramState.hiddenDefaults, ...parsedParams };
      // Do not enforce business-required checks here (backend is authoritative).
      const updates: Partial<Step> = {
        displayName: nextName,
        parameters: parsedParams,
      };
      const selectedRecordType = recordTypeState.resolveRecordTypeForSearch(
        searchState.selectedSearch?.recordType,
      );
      const resolvedRecordType = normalizeRecordType(selectedRecordType);
      if (selectedRecordType) {
        updates.recordType = selectedRecordType;
      }
      if (metadata.kind !== "combine") {
        updates.searchName = nextSearchName;
      }
      if (metadata.kind === "combine") {
        const nextOperator = metadata.operatorValue || step.operator;
        if (!nextOperator) {
          validation.setError("Combine steps require an operator to be selected.");
          return;
        }
        updates.operator = nextOperator as Step["operator"];
        if (nextOperator === "COLOCATE") {
          updates.colocationParams = metadata.colocationParams ?? {
            upstream: 1000,
            downstream: 1000,
            strand: "both",
          };
        } else {
          updates.colocationParams = undefined;
        }
      }
      let validationError: string | null = null;
      if (!searchState.isSearchNameAvailable && metadata.kind === "search") {
        validationError =
          "Cannot be saved: search name is not available for this record type.";
      }
      if (
        metadata.kind === "search" &&
        resolvedRecordType &&
        nextSearchName &&
        !validationError
      ) {
        try {
          const response: SearchValidationResponse = await validateSearchParams(
            siteId,
            resolvedRecordType,
            nextSearchName,
            parsedParams,
          );
          const formatted = formatSearchValidationResponse(response);
          if (formatted.message) {
            validationError = formatted.message;
          }
        } catch (err) {
          validationError = `Cannot be saved: ${toUserMessage(err, "validation failed.")}`;
        }
      }
      updates.validationError = validationError || undefined;
      onUpdate(updates);
      onClose();
    } catch {
      validation.setError("Invalid JSON in parameters");
    }
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

    // Raw params editor
    showRaw: paramState.showRaw,
    setShowRaw: paramState.setShowRaw,
    rawParams: paramState.rawParams,
    setRawParams: paramState.setRawParams,
    error: validation.error,
    setError: validation.setError,
    isLoading: paramState.isLoading,

    // Combine operator
    operatorValue: metadata.operatorValue,
    setOperatorValue: metadata.setOperatorValue,
    colocationParams: metadata.colocationParams,
    setColocationParams: metadata.setColocationParams,

    // Actions
    handleSave,
  };
}

export type StepEditorState = ReturnType<typeof useStepEditorState>;
