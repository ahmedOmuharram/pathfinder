import { useForm } from "@tanstack/react-form";
import type { ParamSpec } from "@pathfinder/shared";
import { isMultiParam } from "@/features/strategy/parameters/spec";

export type ParamFormValues = Record<string, string | string[]>;

function extractDefaults(specs: ParamSpec[]): ParamFormValues {
  const defaults: ParamFormValues = {};
  for (const spec of specs) {
    if (spec.name === "" || spec.isVisible === false) continue;
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
          /* not JSON -- fall through */
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

export { extractDefaults };

export type ParamForm = ReturnType<typeof useParamForm>;

export function useParamForm(specs: ParamSpec[]) {
  const defaultValues = extractDefaults(specs);

  return useForm({
    defaultValues,
    onSubmit: () => {
      // submission handled externally via handleSave
    },
  });
}
