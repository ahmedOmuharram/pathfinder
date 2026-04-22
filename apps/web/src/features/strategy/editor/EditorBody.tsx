"use client";

import type { Step } from "@pathfinder/shared";
import type { StepEditorState } from "./useStepEditorState";
import { SearchTransformBody } from "./SearchTransformBody";
import { CombineBody } from "./CombineBody";

interface EditorBodyProps {
  state: StepEditorState;
  step: Step;
  onSearchChange: (next: string | null) => void;
  onOperatorChange: (operator: string) => void;
  onColocationChange: (next: NonNullable<Step["colocationParams"]>) => void;
  onFieldChanged: (
    name: string,
    value: unknown,
    allValues: Record<string, unknown>,
  ) => void;
  onFieldBlurred: () => void;
}

export function EditorBody({
  state,
  step,
  onSearchChange,
  onOperatorChange,
  onColocationChange,
  onFieldChanged,
  onFieldBlurred,
}: EditorBodyProps) {
  if (state.kind === "combine") {
    return (
      <CombineBody
        operator={state.operatorValue}
        colocationParams={state.colocationParams ?? null}
        onOperatorChange={onOperatorChange}
        onColocationChange={onColocationChange}
      />
    );
  }

  return (
    <SearchTransformBody
      state={state}
      step={step}
      onSearchChange={onSearchChange}
      onFieldChanged={onFieldChanged}
      onFieldBlurred={onFieldBlurred}
    />
  );
}
