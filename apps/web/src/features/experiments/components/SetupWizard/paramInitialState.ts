import type { ParamSpec } from "@pathfinder/shared";
import { parseMultiPickInitial } from "../paramUtils";

/**
 * Build initial parameter values from specs, optionally merging in
 * cloned or suggested values.
 */
export function buildInitialParamsFromSpecs(
  specs: ParamSpec[],
  cloned?: Record<string, unknown> | null,
  suggested?: Record<string, string> | null,
): Record<string, string> {
  const initial: Record<string, string> = {};
  for (const spec of specs) {
    if (cloned && spec.name in cloned) {
      const cv = cloned[spec.name];
      initial[spec.name] = typeof cv === "string" ? cv : cv != null ? String(cv) : "";
    } else if (suggested && spec.name in suggested) {
      initial[spec.name] = suggested[spec.name];
    } else {
      const dflt = spec.initialDisplayValue;
      const raw = typeof dflt === "string" ? dflt : dflt != null ? String(dflt) : "";
      initial[spec.name] = parseMultiPickInitial(spec, raw);
    }
  }
  return initial;
}
