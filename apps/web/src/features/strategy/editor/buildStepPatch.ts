import type { ColocationParams, Step } from "@pathfinder/shared";

export interface BuildPatchArgs {
  step: Step;
  formValues: Record<string, unknown>;
  hiddenDefaults: Record<string, unknown>;
  allowedParamKeys: ReadonlySet<string>;
  operator: string;
  displayName: string;
  colocationParams: ColocationParams | null;
}

function normalizeParamValue(val: unknown): string | string[] {
  if (Array.isArray(val)) return val.map(String);
  if (val == null) return "";
  return String(val);
}

function paramValueEquals(a: string | string[], b: string | string[]): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    return a.every((v, i) => v === b[i]);
  }
  if (Array.isArray(a) || Array.isArray(b)) return false;
  return a === b;
}

export function buildStepPatch(args: BuildPatchArgs): Partial<Step> {
  const baseParams = args.step.parameters ?? {};
  const parameters: Record<string, string | string[]> = {};
  for (const [key, val] of Object.entries(args.formValues)) {
    if (!args.allowedParamKeys.has(key)) continue;
    const next = normalizeParamValue(val);
    const baseRaw = baseParams[key];
    const base = baseRaw === undefined ? null : normalizeParamValue(baseRaw);
    if (base !== null && paramValueEquals(next, base)) continue;
    parameters[key] = next;
  }
  for (const [key, val] of Object.entries(args.hiddenDefaults)) {
    if (val == null) continue;
    const next = normalizeParamValue(val);
    const baseRaw = baseParams[key];
    const base = baseRaw === undefined ? null : normalizeParamValue(baseRaw);
    if (base !== null && paramValueEquals(next, base)) continue;
    parameters[key] = next;
  }

  const patch: Partial<Step> = {};
  if (Object.keys(parameters).length > 0) {
    patch.parameters = parameters;
  }
  if (args.operator !== (args.step.operator ?? "")) {
    patch.operator = args.operator;
  }
  if (args.displayName !== (args.step.displayName ?? "")) {
    patch.displayName = args.displayName;
  }
  const baseColocation = args.step.colocationParams ?? null;
  if (
    JSON.stringify(args.colocationParams ?? null) !==
    JSON.stringify(baseColocation)
  ) {
    patch.colocationParams = args.colocationParams;
  }
  return patch;
}
