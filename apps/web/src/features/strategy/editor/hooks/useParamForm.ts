import { useState } from "react";
import { useForm } from "@tanstack/react-form";
import type { ParamSpec } from "@pathfinder/shared";
import type { StepParameters } from "@/lib/strategyGraph/types";
import { isMultiParam } from "@/features/strategy/parameters/spec";

export type ParamFormValues = Record<string, string | string[]>;

function coerceToMulti(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.map(String);
  if (raw == null) return [];
  if (typeof raw === "string") {
    if (raw.startsWith("[")) {
      try {
        const parsed: unknown = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed.map(String);
      } catch {
        /* fall through to plain string handling */
      }
    }
    return raw.length > 0 ? [raw] : [];
  }
  return [String(raw)];
}

function coerceToSingle(raw: unknown): string {
  if (raw == null) return "";
  if (typeof raw === "string") return raw;
  if (Array.isArray(raw)) return raw.length > 0 ? String(raw[0]) : "";
  return String(raw);
}

function extractDefaults(
  specs: ParamSpec[],
  override?: StepParameters,
): ParamFormValues {
  const defaults: ParamFormValues = {};
  for (const spec of specs) {
    if (spec.name === "" || spec.isVisible === false) continue;
    const overrideHas =
      override !== undefined &&
      Object.prototype.hasOwnProperty.call(override, spec.name);
    const source: unknown = overrideHas
      ? override[spec.name]
      : spec.initialDisplayValue;
    const result = isMultiParam(spec) ? coerceToMulti(source) : coerceToSingle(source);
    defaults[spec.name] = result;
  }
  return defaults;
}

export { extractDefaults };

function useParamFormInternal(specs: ParamSpec[], override?: StepParameters) {
  return useForm({
    defaultValues: extractDefaults(specs, override),
    onSubmit: () => {
      // submission handled externally via mutations
    },
  });
}

export type ParamForm = ReturnType<typeof useParamFormInternal>;

export interface UseParamFormResult {
  form: ParamForm;
  /**
   * `true` once the form has reset to defaults built from the current
   * `(specs, override)` inputs. `false` on initial mount when `specs` is empty
   * (defaults map is `{}` and contains nothing meaningful to save). Consumers
   * gate autosave on this so user edits are not overwritten by stale form
   * state, and so the WDK defaults shown briefly before saved values arrive
   * are not autosaved back over the user's actual values.
   */
  hydrated: boolean;
}

/**
 * Form bound to the current `paramSpecs`. When `paramSpecs` identity OR the
 * `override` identity changes (e.g. user picks a different searchName, or a
 * step's persisted `parameters` arrive), the form resets to the new defaults
 * via the render-time prevValue pattern (no `useEffect`).
 *
 * `hydrated` is `false` on first mount (defaults built from current inputs)
 * only when there are zero specs, but otherwise `true` after the synchronous
 * reset that follows any input change.
 */
export function useParamForm(
  specs: ParamSpec[],
  override?: StepParameters,
): UseParamFormResult {
  const form = useParamFormInternal(specs, override);

  const [prevSpecs, setPrevSpecs] = useState(specs);
  const [prevOverride, setPrevOverride] = useState(override);
  const [hydrated, setHydrated] = useState(specs.length > 0);

  if (specs !== prevSpecs || override !== prevOverride) {
    setPrevSpecs(specs);
    setPrevOverride(override);
    form.reset(extractDefaults(specs, override));
    setHydrated(specs.length > 0);
  }

  return { form, hydrated };
}
