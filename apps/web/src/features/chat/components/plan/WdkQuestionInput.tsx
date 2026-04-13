"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import type { ParamSpec } from "@pathfinder/shared";
import { useForm, useWatch } from "react-hook-form";

import { StepParamFields } from "@/features/strategy/editor/components/StepParamFields";
import { buildParamSchema } from "@/features/strategy/editor/schema/paramSchema";
import { useParamSpecs } from "@/lib/hooks/useParamSpecs";
import type { PlannedStep } from "@/lib/types/plan";
import {
  buildFormDefaults,
  buildVocabOptions,
} from "./planParameterEditorUtils";

interface WdkQuestionInputProps {
  siteId: string;
  step: PlannedStep;
  paramName: string;
  onSubmit: (value: unknown) => void;
  disabled: boolean;
}

/**
 * Renders a WDK-aware parameter widget for a plan question.
 *
 * The question's ``relatedStep`` + ``relatedParam`` identify a real WDK
 * parameter — the backend enforces this. Freeform clarification questions
 * (no ``relatedParam``) are handled by PlanQuestionCard's text input
 * branch and never reach this component.
 */
export function WdkQuestionInput({
  siteId,
  step,
  paramName,
  onSubmit,
  disabled,
}: WdkQuestionInputProps) {
  const { paramSpecs, isLoading } = useParamSpecs(
    siteId,
    step.recordType,
    step.searchName,
  );
  const targetSpec = paramSpecs.find((s) => s.name === paramName);

  if (isLoading) {
    return (
      <p className="text-xs text-muted-foreground">
        Loading parameter controls...
      </p>
    );
  }

  if (targetSpec == null) {
    return null;
  }

  return (
    <SingleParamWidget
      spec={targetSpec}
      siteId={siteId}
      recordType={step.recordType}
      searchName={step.searchName}
      onSubmit={onSubmit}
      disabled={disabled}
    />
  );
}

function SingleParamWidget({
  spec,
  siteId,
  recordType,
  searchName,
  onSubmit,
  disabled,
}: {
  spec: ParamSpec;
  siteId: string;
  recordType: string;
  searchName: string;
  onSubmit: (value: unknown) => void;
  disabled: boolean;
}) {
  const specs = [spec];
  const defaultValues = buildFormDefaults(specs, {});
  const form = useForm({
    resolver: zodResolver(buildParamSchema(specs)),
    defaultValues,
    mode: "onBlur",
  });
  const watchedValues = useWatch({ control: form.control });
  const currentValue = (watchedValues as Record<string, unknown>)[spec.name];

  const hasValue =
    currentValue != null &&
    currentValue !== "" &&
    !(Array.isArray(currentValue) && currentValue.length === 0);

  return (
    <div className="space-y-2">
      <fieldset disabled={disabled}>
        <StepParamFields
          form={form}
          paramSpecs={specs}
          vocabOptions={buildVocabOptions(specs)}
          siteId={siteId}
          recordType={recordType}
          searchName={searchName}
        />
      </fieldset>
      <button
        type="button"
        disabled={disabled || !hasValue}
        onClick={() => onSubmit(currentValue)}
        className="rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
      >
        Submit
      </button>
    </div>
  );
}
