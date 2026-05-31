import { z } from "zod";
import type { ParamSpec } from "@pathfinder/shared";
import { isMultiParam } from "@/features/strategy/parameters/spec";

export function buildFieldSchema(spec: ParamSpec): z.ZodType {
  const name = spec.name;

  if (isMultiParam(spec)) {
    let field = z.array(z.string());
    if (spec.allowEmptyValue === false) {
      field = field.min(1, {
        message: `${spec.displayName ?? name} requires at least one selection`,
      });
    }
    return field;
  }

  const base = z.string();

  if (spec.isNumber === true) {
    const numericPattern = /^-?\d+(\.\d+)?$/;
    if (spec.allowEmptyValue === false) {
      return base
        .min(1, { message: `${spec.displayName ?? name} is required` })
        .refine((val) => numericPattern.test(val), {
          message: `${spec.displayName ?? name} must be a number`,
        });
    }
    return base.refine((val) => val === "" || numericPattern.test(val), {
      message: `${spec.displayName ?? name} must be a number`,
    });
  }

  if (spec.allowEmptyValue === false) {
    return base.min(1, { message: `${spec.displayName ?? name} is required` });
  }

  return base;
}

export function buildFieldSchemaMap(specs: ParamSpec[]): Map<string, z.ZodType> {
  const map = new Map<string, z.ZodType>();
  for (const spec of specs) {
    if (!spec.name) continue;
    if (spec.isVisible === false) continue;
    map.set(spec.name, buildFieldSchema(spec));
  }
  return map;
}

export function buildParamSchema(
  specs: ParamSpec[],
): z.ZodObject<Record<string, z.ZodType>> {
  const shape: Record<string, z.ZodType> = {};
  for (const [name, schema] of buildFieldSchemaMap(specs)) {
    shape[name] = schema;
  }
  return z.object(shape);
}
