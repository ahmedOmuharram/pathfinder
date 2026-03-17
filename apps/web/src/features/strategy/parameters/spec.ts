export interface ParamSpec {
  name?: string;
  displayName?: string | null;
  help?: string | null;
  type?: string;
  allowEmptyValue?: boolean;
  allowMultipleValues?: boolean | null;
  multiPick?: boolean | null;
  vocabulary?: unknown;
  defaultValue?: unknown;
  initialDisplayValue?: unknown;
  minSelectedCount?: number | null;
  maxSelectedCount?: number | null;
  min?: number | null;
  max?: number | null;
  isNumber?: boolean;
  increment?: number | null;
  countOnlyLeaves?: boolean;
  /** WDK display type: "treeBox", "typeAhead", "select", "checkBox", or "" */
  displayType?: string | null;
  /** Whether this param is visible to users (false = hidden/structural) */
  isVisible?: boolean;
  /** WDK param group: "empty", "dynamicParams", "advancedParams", "_hidden" */
  group?: string | null;
  /** Param names whose vocabulary depends on this param's value */
  dependentParams?: string[];
  values?: unknown;
  items?: unknown;
  terms?: unknown;
  options?: unknown;
  allowedValues?: unknown;
  [key: string]: unknown;
}

export function isMultiParam(spec: ParamSpec) {
  if (spec.allowMultipleValues || spec.multiPick) return true;
  if (typeof spec.maxSelectedCount === "number" && spec.maxSelectedCount > 1) {
    return true;
  }
  return (spec.type || "").toLowerCase().includes("multi");
}
