import { z } from "zod";
import type { ParamSpec } from "@pathfinder/shared";
import { isMultiParam } from "@/features/strategy/parameters/spec";

/**
 * Build a dynamic Zod schema from WDK parameter specs.
 *
 * Each param maps to a Zod field based on its type, constraints, and
 * multi-pick status. Hidden params are excluded (they use server defaults).
 *
 * The resulting schema validates Record<string, string | string[]>,
 * matching WDK's SearchConfig.parameters.
 */
export function buildParamSchema(
  specs: ParamSpec[],
): z.ZodObject<Record<string, z.ZodType>> {
  const shape: Record<string, z.ZodType> = {};

  for (const spec of specs) {
    const name = spec.name;
    if (!name) continue;
    if (spec.isVisible === false) continue;

    if (isMultiParam(spec)) {
      let field = z.array(z.string());
      if (spec.allowEmptyValue === false) {
        field = field.min(1, { message: `${spec.displayName ?? name} requires at least one selection` });
      }
      shape[name] = field;
      continue;
    }

    const base = z.string();

    if (spec.isNumber === true) {
      // WDK sends numbers as strings. Validate the string is a strict decimal
      // number — rejects hex ("0xff"), whitespace (" 1"), and other coercible
      // values that Number() would silently accept.
      const numericPattern = /^-?\d+(\.\d+)?$/;
      if (spec.allowEmptyValue === false) {
        shape[name] = base
          .min(1, { message: `${spec.displayName ?? name} is required` })
          .refine(
            (val) => numericPattern.test(val),
            { message: `${spec.displayName ?? name} must be a number` },
          );
      } else {
        shape[name] = base.refine(
          (val) => val === "" || numericPattern.test(val),
          { message: `${spec.displayName ?? name} must be a number` },
        );
      }
      continue;
    }

    if (spec.allowEmptyValue === false) {
      shape[name] = base.min(1, { message: `${spec.displayName ?? name} is required` });
      continue;
    }

    shape[name] = base;
  }

  return z.object(shape);
}
