"use client";

import { useRef } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import type { ParamSpec } from "@pathfinder/shared";
import {
  useForm,
  useFormState,
  useWatch,
} from "react-hook-form";
import { useEventCallback, useIsomorphicLayoutEffect } from "usehooks-ts";

import { StepParamFields } from "@/features/strategy/editor/components/StepParamFields";
import { buildParamSchema } from "@/features/strategy/editor/schema/paramSchema";
import { coerceParametersForSpecs } from "@/features/strategy/parameters/coerce";
import { useParamSpecs } from "@/lib/hooks/useParamSpecs";
import type { PlannedStep } from "@/lib/types/plan";
import type { StepParameters } from "@/lib/strategyGraph/types";
import {
  areParamValuesEquivalent,
  buildFormDefaults,
  buildVocabOptions,
  extractPlannedValues,
  getEditableSpecs,
  isFieldDirty,
  stableStringify,
} from "@/features/chat/components/plan/planParameterEditorUtils";

interface PlanParameterEditorProps {
  siteId: string;
  step: PlannedStep;
  onParamChange: (paramName: string, value: unknown) => void;
  disabled: boolean;
}

export function PlanParameterEditor({
  siteId,
  step,
  onParamChange,
  disabled,
}: PlanParameterEditorProps) {
  const plannedParams = Object.values(step.parameters);
  const plannedValues = extractPlannedValues(plannedParams);
  const canFetchSpecs =
    plannedParams.length > 0 &&
    step.stepType === "leaf" &&
    siteId !== "" &&
    step.recordType !== "" &&
    step.searchName !== "";

  const { paramSpecs, isLoading } = useParamSpecs({
    siteId,
    recordType: step.recordType,
    searchName: step.searchName,
    selectedSearch: null,
    isSearchNameAvailable: true,
    apiRecordTypeValue: step.recordType,
    resolveRecordTypeForSearch: () => step.recordType,
    contextValues: plannedValues,
    enabled: canFetchSpecs,
  });
  const editableSpecs = getEditableSpecs(plannedParams, paramSpecs);

  if (plannedParams.length === 0) return null;

  if (isLoading && editableSpecs.length === 0 && canFetchSpecs) {
    return (
      <p className="text-xs text-muted-foreground">
        Loading WDK parameter controls...
      </p>
    );
  }

  if (editableSpecs.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No editable parameter controls available for this step.
      </p>
    );
  }

  return (
    <WdkParameterFields
      siteId={siteId}
      step={step}
      paramSpecs={editableSpecs}
      plannedValues={plannedValues}
      disabled={disabled}
      onParamChange={onParamChange}
    />
  );
}

function WdkParameterFields({
  siteId,
  step,
  paramSpecs,
  plannedValues,
  disabled,
  onParamChange,
}: {
  siteId: string;
  step: PlannedStep;
  paramSpecs: ParamSpec[];
  plannedValues: StepParameters;
  disabled: boolean;
  onParamChange: (paramName: string, value: unknown) => void;
}) {
  const defaultValues = buildFormDefaults(paramSpecs, plannedValues);
  const form = useForm({
    resolver: zodResolver(buildParamSchema(paramSpecs)),
    defaultValues,
    values: defaultValues,
    resetOptions: { keepDirtyValues: true },
    mode: "onBlur",
  });
  const watchedValues = useWatch({ control: form.control });
  const { dirtyFields } = useFormState({ control: form.control });
  const lastSentRef = useRef<Record<string, string>>({});
  const stableOnParamChange = useEventCallback(onParamChange);

  useIsomorphicLayoutEffect(() => {
    const currentValues = watchedValues as StepParameters;
    const coercedValues = coerceParametersForSpecs(
      currentValues,
      paramSpecs,
      { allowStringParsing: false },
    );
    const dirtyFieldMap = dirtyFields as Record<string, unknown>;

    for (const spec of paramSpecs) {
      if (spec.name === "") continue;
      const currentValue = coercedValues[spec.name];
      const originalValue = plannedValues[spec.name];
      const changed = isFieldDirty(dirtyFieldMap[spec.name])
        && !areParamValuesEquivalent(currentValue, originalValue, spec);
      const nextValue = changed ? currentValue : originalValue;
      const sentKey = stableStringify({ changed, value: nextValue });
      if (lastSentRef.current[spec.name] === sentKey) continue;
      lastSentRef.current[spec.name] = sentKey;
      stableOnParamChange(spec.name, nextValue);
    }
  }, [dirtyFields, paramSpecs, plannedValues, stableOnParamChange, watchedValues]);

  return (
    <fieldset disabled={disabled} className="space-y-3">
      <StepParamFields
        form={form}
        paramSpecs={paramSpecs}
        vocabOptions={buildVocabOptions(paramSpecs)}
        siteId={siteId}
        recordType={step.recordType}
        searchName={step.searchName}
      />
    </fieldset>
  );
}
