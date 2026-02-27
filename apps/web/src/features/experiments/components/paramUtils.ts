import type { OptimizeSpec, ParamSpec } from "@pathfinder/shared";
import { extractVocabOptions } from "@/features/strategy/editor/components/stepEditorUtils";

export interface VocabEntry {
  value: string;
  display: string;
}

export function flattenVocab(vocab: unknown): VocabEntry[] {
  return extractVocabOptions(vocab).map((o) => ({
    value: o.value,
    display: o.label,
  }));
}

export function isOptimizable(spec: ParamSpec): boolean {
  if (spec.type === "input-step") return false;
  return true;
}

export function isParamRequired(spec: ParamSpec): boolean {
  if (spec.allowEmptyValue === true) return false;
  if (spec.isReadOnly || spec.isVisible === false) return false;
  if (spec.type === "input-step") return false;
  return true;
}

export function isMultiPickParam(spec: ParamSpec): boolean {
  return spec.type === "multi-pick-vocabulary" || spec.multiPick === true;
}

export function isParamEmpty(spec: ParamSpec, value: string): boolean {
  if (value == null || value === "") return true;
  if (isMultiPickParam(spec) && value === "[]") return true;
  return false;
}

export function parseMultiPickInitial(spec: ParamSpec, raw: string): string {
  if (!isMultiPickParam(spec) || !raw.startsWith("[")) return raw;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.join(",");
  } catch {
    /* not valid JSON */
  }
  return raw;
}

export function resolveDisplayValue(value: string, spec?: ParamSpec | null): string {
  if (!spec?.vocabulary) return value;
  const entries = flattenVocab(spec.vocabulary);
  const match = entries.find((e) => e.value === value);
  return match?.display ?? value;
}

function isNumericParam(spec: ParamSpec): boolean {
  const t = spec.type?.toLowerCase() ?? "";
  if (t === "number" || t === "number-range" || t === "integer" || t === "float")
    return true;
  if (spec.isNumber === true) return true;
  return false;
}

function inferNumericRange(spec: ParamSpec): {
  min: number;
  max: number;
  step?: number;
} {
  const explicitMin = spec.min ?? spec.minValue;
  const explicitMax = spec.max ?? spec.maxValue;
  if (explicitMin != null && explicitMax != null) {
    return { min: explicitMin, max: explicitMax, step: spec.increment ?? undefined };
  }
  const initial =
    typeof spec.initialDisplayValue === "string"
      ? parseFloat(spec.initialDisplayValue)
      : typeof spec.initialDisplayValue === "number"
        ? spec.initialDisplayValue
        : NaN;
  if (!isNaN(initial) && initial > 0) {
    const lo = explicitMin ?? 0;
    const hi = explicitMax ?? Math.max(initial * 10, initial + 10);
    return { min: lo, max: hi, step: spec.increment ?? undefined };
  }
  return {
    min: explicitMin ?? 0,
    max: explicitMax ?? 100,
    step: spec.increment ?? undefined,
  };
}

/**
 * Build an ``OptimizeSpec`` map for every optimisable parameter.
 *
 * Used by the "Optimize This" action to pre-select all params for
 * optimization when transitioning from an evaluation result.
 */
export function buildAutoOptimizeSpecs(specs: ParamSpec[]): Map<string, OptimizeSpec> {
  const map = new Map<string, OptimizeSpec>();
  for (const spec of specs) {
    if (!isOptimizable(spec)) continue;
    if (isNumericParam(spec)) {
      const range = inferNumericRange(spec);
      map.set(spec.name, {
        name: spec.name,
        type: spec.type === "integer" ? "integer" : "numeric",
        min: range.min,
        max: range.max,
        step: range.step,
      });
    } else {
      const vocab = spec.vocabulary ? flattenVocab(spec.vocabulary) : [];
      if (vocab.length > 0) {
        map.set(spec.name, {
          name: spec.name,
          type: "categorical",
          choices: vocab.map((e) => e.value),
        });
      }
    }
  }
  return map;
}

export function buildDisplayMap(
  parameters: Record<string, string>,
  paramSpecs: ParamSpec[],
): Record<string, string> {
  const map: Record<string, string> = {};
  for (const [key, value] of Object.entries(parameters)) {
    const spec = paramSpecs.find((s) => s.name === key);
    if (!spec?.vocabulary) continue;
    const entries = flattenVocab(spec.vocabulary);
    if (isMultiPickParam(spec)) {
      const vals = value.split(",").filter(Boolean);
      const displays = vals
        .map((v) => entries.find((e) => e.value === v)?.display ?? v)
        .join(", ");
      if (displays !== value) map[key] = displays;
    } else {
      const match = entries.find((e) => e.value === value);
      if (match && match.display !== value) map[key] = match.display;
    }
  }
  return map;
}
