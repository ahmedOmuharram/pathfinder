import { useCallback, useEffect, useMemo, useRef } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { ParamSpec } from "@pathfinder/shared";
import { buildParamSchema } from "../schema/paramSchema";
import { isMultiParam } from "@/features/strategy/parameters/spec";

/**
 * Extract default values from WDK param specs.
 * Single-pick -> string, multi-pick -> string[].
 */
function extractDefaults(specs: ParamSpec[]): Record<string, string | string[]> {
  const defaults: Record<string, string | string[]> = {};
  for (const spec of specs) {
    if (spec.name === "" || !spec.isVisible) continue;
    const initial = spec.initialDisplayValue;
    if (isMultiParam(spec)) {
      if (typeof initial === "string" && initial.startsWith("[")) {
        try {
          const parsed: unknown = JSON.parse(initial);
          if (Array.isArray(parsed)) {
            defaults[spec.name] = parsed.map(String);
            continue;
          }
        } catch {
          /* not JSON — fall through */
        }
      }
      const str = typeof initial === "string" ? initial : String(initial ?? "");
      defaults[spec.name] = str.length > 0 ? [str] : [];
    } else {
      defaults[spec.name] = typeof initial === "string" ? initial : String(initial ?? "");
    }
  }
  return defaults;
}

/**
 * Form hook for WDK search parameter editing.
 *
 * Builds a dynamic Zod schema from param specs, initializes with WDK
 * defaults, and resets when specs change (search switch).
 *
 * IMPORTANT: `specs` must be referentially stable (e.g. from useState or
 * useMemo in the caller). Passing a new array on every render will cause
 * infinite re-renders.
 */
export function useParamForm(specs: ParamSpec[]) {
  const schema = useMemo(() => buildParamSchema(specs), [specs]);
  const defaultValues = useMemo(() => extractDefaults(specs), [specs]);

  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues,
    mode: "onBlur",
  });

  // Stable reset callback — form.reset is not referentially stable in RHF,
  // and including `form` in useEffect deps causes infinite re-renders when
  // formState subscriptions (isDirty, dirtyFields) are active.
  const formResetRef = useRef(form.reset);
  const defaultValuesRef = useRef(defaultValues);
  useEffect(() => {
    formResetRef.current = form.reset;
    defaultValuesRef.current = defaultValues;
  });

  const stableReset = useCallback((values: Record<string, string | string[]>) => {
    formResetRef.current(values);
  }, []);

  const prevSpecsRef = useRef(specs);

  // Reset form when specs change (user switched search).
  useEffect(() => {
    if (prevSpecsRef.current === specs) return;
    prevSpecsRef.current = specs;
    stableReset(defaultValuesRef.current);
  }, [specs, stableReset]);

  return form;
}
