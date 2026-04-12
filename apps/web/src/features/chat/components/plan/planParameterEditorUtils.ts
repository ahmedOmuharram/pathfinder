import type { FieldValues } from "react-hook-form";
import type { ParamSpec } from "@pathfinder/shared";

import { extractSpecVocabulary } from "@/features/strategy/editor/components/stepEditorUtils";
import { coerceMultiValue } from "@/features/strategy/parameters/coerce";
import { isMultiParam } from "@/features/strategy/parameters/spec";
import type { PlannedParameter } from "@/lib/types/plan";
import type { StepParameters } from "@/lib/strategyGraph/types";
import { extractVocabOptions, type VocabOption } from "@/lib/utils/vocab";

export function getEditableSpecs(
  plannedParams: PlannedParameter[],
  paramSpecs: ParamSpec[],
): ParamSpec[] {
  const specByName = new Map(paramSpecs.map((spec) => [spec.name, spec]));
  return plannedParams.flatMap((param) => {
    const spec = specByName.get(param.name);
    if (spec == null) return [];
    return [mergePlannedParamHints(spec, param)];
  });
}

function mergePlannedParamHints(
  spec: ParamSpec,
  param: PlannedParameter,
): ParamSpec {
  const hasSpecVocabulary = extractSpecVocabulary(spec) != null;
  const plannedVocabulary =
    !hasSpecVocabulary && param.options != null ? param.options : undefined;
  return {
    ...spec,
    displayName: spec.displayName ?? param.displayName,
    help: spec.help ?? param.description ?? null,
    initialDisplayValue: param.value ?? spec.initialDisplayValue,
    ...(plannedVocabulary !== undefined ? { vocabulary: plannedVocabulary } : {}),
  };
}

export function extractPlannedValues(
  params: PlannedParameter[],
): StepParameters {
  const values: StepParameters = {};
  for (const param of params) {
    values[param.name] = param.value;
  }
  return values;
}

export function buildFormDefaults(
  specs: ParamSpec[],
  plannedValues: StepParameters,
): FieldValues {
  const defaults: FieldValues = {};
  for (const spec of specs) {
    if (spec.name === "") continue;
    defaults[spec.name] = toFormValue(plannedValues[spec.name], spec);
  }
  return defaults;
}

function toFormValue(value: unknown, spec: ParamSpec): string | string[] {
  if (isMultiParam(spec)) {
    return coerceMultiValue(value, {
      allowStringParsing: true,
      allowCsv: true,
    });
  }
  if (value == null) return "";
  if (Array.isArray(value)) return value.length > 0 ? String(value[0]) : "";
  return String(value);
}

export function buildVocabOptions(
  specs: ParamSpec[],
): Record<string, VocabOption[]> {
  return specs.reduce<Record<string, VocabOption[]>>((acc, spec) => {
    if (spec.name === "") return acc;
    const vocabulary = extractSpecVocabulary(spec);
    if (vocabulary != null) {
      acc[spec.name] = extractVocabOptions(vocabulary);
    }
    return acc;
  }, {});
}

export function isFieldDirty(value: unknown): boolean {
  if (value === true) return true;
  if (Array.isArray(value)) return value.some(isFieldDirty);
  if (value != null && typeof value === "object") {
    return Object.values(value).some(isFieldDirty);
  }
  return false;
}

export function areParamValuesEquivalent(
  currentValue: unknown,
  originalValue: unknown,
  spec: ParamSpec,
): boolean {
  if (isMultiParam(spec)) {
    const current = coerceMultiValue(currentValue, {
      allowStringParsing: true,
      allowCsv: true,
    }).sort();
    const original = coerceMultiValue(originalValue, {
      allowStringParsing: true,
      allowCsv: true,
    }).sort();
    return stableStringify(current) === stableStringify(original);
  }
  return scalarComparable(currentValue) === scalarComparable(originalValue);
}

function scalarComparable(value: unknown): string {
  if (value == null) return "";
  if (Array.isArray(value)) return value.length > 0 ? String(value[0]) : "";
  return String(value);
}

export function stableStringify(value: unknown): string {
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
