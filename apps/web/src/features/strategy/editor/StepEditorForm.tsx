"use client";

import { StepCombineOperatorSelect } from "./components/StepCombineOperatorSelect";
import { StepNameFields } from "./components/StepNameFields";
import { StepParamFields } from "./components/StepParamFields";
import { StepSearchSelector } from "./components/StepSearchSelector";
import type { StepEditorState } from "./useStepEditorState";

interface StepEditorFormProps {
  state: StepEditorState;
}

export function StepEditorForm({ state }: StepEditorFormProps) {
  return (
    <div className="max-h-[80vh] space-y-4 overflow-y-auto px-5 py-4">
      {state.stepValidationError != null && state.stepValidationError !== "" && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {state.stepValidationError}
        </div>
      )}
      <StepNameFields oldName={state.oldName ?? ""} />

      {(state.kind === "search" || state.kind === "transform") && (
        <>
          <StepSearchSelector
            siteId={state.siteId}
            stepType={state.kind}
            recordTypeFilter={state.recordTypeFilter}
            onRecordTypeFilterChange={state.setRecordTypeFilter}
            filteredRecordTypes={state.filteredRecordTypes}
            normalizedRecordTypeValue={state.normalizedRecordTypeValue}
            onRecordTypeValueChange={state.setRecordTypeValue}
            editableSearchName={state.editableSearchName}
            onSearchNameChange={state.setEditableSearchName}
            searchOptions={state.searchOptions}
            filteredSearchOptions={state.filteredSearchOptions}
            searchName={state.searchName}
            selectedSearch={state.selectedSearch}
            isSearchNameAvailable={state.isSearchNameAvailable}
            recordTypeValue={state.recordTypeValue ?? null}
            recordType={state.recordType}
            recordTypeOptions={state.recordTypeOptions}
          />

          <StepParamFields
            form={state.form}
            paramSpecs={state.paramSpecs}
            vocabOptions={state.vocabOptions}
            siteId={state.siteId}
            recordType={state.recordType ?? ""}
            searchName={state.searchName}
          />
        </>
      )}

      {state.kind === "combine" && (
        <StepCombineOperatorSelect
          operatorValue={state.operatorValue}
          onOperatorChange={state.setOperatorValue}
          colocationParams={state.colocationParams}
          onColocationParamsChange={state.setColocationParams}
        />
      )}
    </div>
  );
}
