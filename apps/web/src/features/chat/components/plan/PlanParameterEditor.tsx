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
import type { PlannedParameter, PlannedStep } from "@/lib/types/plan";
import type { StepParameters } from "@/lib/strategyGraph/types";
import { PlanParameterField } from "@/features/chat/components/plan/PlanParameterField";
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
  const editableNames = new Set(editableSpecs.map((spec) => spec.name));
  const fallbackParams = plannedParams.filter(
    (param) => !editableNames.has(param.name),
  );

  if (isLoading && editableSpecs.length === 0 && canFetchSpecs) {
    return (
      <p className="text-xs text-muted-foreground">
        Loading WDK parameter controls...
      </p>
    );
  }

  if (editableSpecs.length === 0) {
    return (
      <LegacyParameterFields
        params={plannedParams}
        disabled={disabled}
        onParamChange={onParamChange}
      />
    );
  }

  return (
    <div className="space-y-3">
      <WdkParameterFields
        siteId={siteId}
        step={step}
        paramSpecs={editableSpecs}
        plannedValues={plannedValues}
        disabled={disabled}
        onParamChange={onParamChange}
      />
      {fallbackParams.length > 0 && (
        <div className="space-y-3 border-t border-border pt-3">
          <p className="text-[11px] text-muted-foreground">
            Some parameters are not described by the current WDK spec, so they
            use the raw fallback editor.
          </p>
          <LegacyParameterFields
            params={fallbackParams}
            disabled={disabled}
            onParamChange={onParamChange}
          />
        </div>
      )}
    </div>
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

function LegacyParameterFields({
  params,
  disabled,
  onParamChange,
}: {
  params: PlannedParameter[];
  disabled: boolean;
  onParamChange: (paramName: string, value: unknown) => void;
}) {
  return (
    <div className="space-y-3">
      {params.map((param) => (
        <PlanParameterField
          key={param.name}
          param={param}
          onChange={onParamChange}
          disabled={disabled}
        />
      ))}
    </div>
  );
}
