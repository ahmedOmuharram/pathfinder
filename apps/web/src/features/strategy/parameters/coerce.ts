import type { ParamSpec } from "@/features/strategy/parameters/spec";
import { isMultiParam } from "@/features/strategy/parameters/spec";

type CoerceOptions = {
  allowStringParsing?: boolean;
  allowCsv?: boolean;
};

const coerceArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];
  return value.map((entry) => String(entry)).filter(Boolean);
};

export function coerceMultiValue(
  value: unknown,
  options: CoerceOptions = {},
): string[] {
  const { allowStringParsing = false, allowCsv = false } = options;
  if (value === null || value === undefined) return [];

  if (Array.isArray(value)) {
    const values = coerceArray(value);
    return values.includes("@@fake@@") ? ["@@fake@@"] : values;
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
      try {
        const parsed = JSON.parse(trimmed);
        if (Array.isArray(parsed)) {
          const values = coerceArray(parsed);
          return values.includes("@@fake@@") ? ["@@fake@@"] : values;
        }
      } catch {
        // Fall through to CSV parsing if enabled.
      }
    }
    if (allowStringParsing && allowCsv) {
      const values = trimmed
        .split(",")
        .map((entry) => entry.trim())
        .filter(Boolean);
      return values.includes("@@fake@@") ? ["@@fake@@"] : values;
    }
    if (trimmed === "@@fake@@") return ["@@fake@@"];
    return trimmed ? [trimmed] : [];
  }

  if (value === "@@fake@@") return ["@@fake@@"];
  return [String(value)];
}

function coerceScalarValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.length > 0 ? value[0] : undefined;
  }
  return value;
}

export function coerceParametersForSpecs(
  params: Record<string, unknown>,
  specs: ParamSpec[],
  options: CoerceOptions = {},
): Record<string, unknown> {
  const next: Record<string, unknown> = { ...params };
  for (const spec of specs) {
    if (!spec.name) continue;
    const rawValue = params[spec.name];
    if (isMultiParam(spec)) {
      next[spec.name] = coerceMultiValue(rawValue, options);
    } else {
      next[spec.name] = coerceScalarValue(rawValue);
    }
  }
  return next;
}
