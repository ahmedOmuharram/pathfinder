export interface ParamSpec {
  name?: string;
  displayName?: string | null;
  help?: string;
  type?: string;
  allowEmptyValue?: boolean;
  allowMultipleValues?: boolean | null;
  multiPick?: boolean | null;
  vocabulary?: unknown;
  defaultValue?: unknown;
  minSelectedCount?: number | null;
  maxSelectedCount?: number | null;
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
