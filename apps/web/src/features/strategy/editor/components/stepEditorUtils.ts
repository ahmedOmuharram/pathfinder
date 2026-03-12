import type { ParamSpec } from "@/features/strategy/parameters/spec";

export function extractSpecVocabulary(spec: ParamSpec): unknown {
  return (
    spec.vocabulary ??
    spec.values ??
    spec.items ??
    spec.terms ??
    spec.options ??
    spec.allowedValues
  );
}
