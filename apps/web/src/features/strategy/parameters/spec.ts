export interface ParamSpec {
  name?: string;
  displayName?: string;
  help?: string;
  type?: string;
  allowEmptyValue?: boolean;
  allowMultipleValues?: boolean;
  multiPick?: boolean;
  vocabulary?: unknown;
  defaultValue?: unknown;
  minSelectedCount?: number;
  maxSelectedCount?: number;
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
