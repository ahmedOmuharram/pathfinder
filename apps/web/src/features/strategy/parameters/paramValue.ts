import type { Step } from "@pathfinder/shared";
import type { FilterTermClause } from "@pathfinder/shared/generated/types/FilterTermClause";
import type { ParamSpec } from "@/features/strategy/parameters/spec";

export type ParamValue = NonNullable<Step["parameters"]>[string];
export type ParamValueMap = NonNullable<Step["parameters"]>;

export function paramValueToRaw(v: ParamValue): string | string[] {
  switch (v.type) {
    case "string":
    case "date":
    case "timestamp":
    case "single-pick-vocabulary":
      return v.value;
    case "number":
      return String(v.value);
    case "multi-pick-vocabulary":
      return v.values;
    case "number-range":
    case "date-range":
      return `${v.min ?? ""}-${v.max ?? ""}`;
    case "input-dataset":
      return v.datasetId;
    case "input-step":
      return v.stepId;
    case "filter":
      return JSON.stringify(v.filters ?? []);
  }
}

function parseRange(raw: string | string[]): { min: string; max: string } {
  const s = typeof raw === "string" ? raw : "";
  const idx = s.indexOf("-", 1);
  if (idx <= 0) return { min: s, max: "" };
  return { min: s.slice(0, idx), max: s.slice(idx + 1) };
}

function toNumberOrNull(s: string): number | null {
  if (s === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function asString(raw: string | string[]): string {
  if (typeof raw === "string") return raw;
  return raw[0] ?? "";
}

function asStringArray(raw: string | string[]): string[] {
  if (Array.isArray(raw)) return raw;
  return raw === "" ? [] : [raw];
}

export function rawToParamValue(
  spec: ParamSpec,
  raw: string | string[],
): ParamValue {
  switch (spec.type) {
    case "number":
      return { type: "number", value: Number(asString(raw)) };
    case "number-range": {
      const { min, max } = parseRange(raw);
      return {
        type: "number-range",
        min: toNumberOrNull(min),
        max: toNumberOrNull(max),
      };
    }
    case "date":
      return { type: "date", value: asString(raw) };
    case "date-range": {
      const { min, max } = parseRange(raw);
      return {
        type: "date-range",
        min: min === "" ? null : min,
        max: max === "" ? null : max,
      };
    }
    case "timestamp":
      return { type: "timestamp", value: asString(raw) };
    case "single-pick-vocabulary":
      return { type: "single-pick-vocabulary", value: asString(raw) };
    case "multi-pick-vocabulary":
      return { type: "multi-pick-vocabulary", values: asStringArray(raw) };
    case "input-dataset":
      return { type: "input-dataset", datasetId: asString(raw) };
    case "input-step":
      return { type: "input-step", stepId: asString(raw) };
    case "filter": {
      const s = asString(raw);
      const parsed: unknown = s === "" ? [] : JSON.parse(s);
      const filters: FilterTermClause[] = Array.isArray(parsed)
        ? (parsed as FilterTermClause[])
        : [];
      return { type: "filter", filters };
    }
    default:
      return { type: "string", value: asString(raw) };
  }
}
