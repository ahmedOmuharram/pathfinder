import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { ParamSpec } from "@pathfinder/shared";
import { buildParamSchema } from "../schema/paramSchema";
import { isMultiParam } from "@/features/strategy/parameters/spec";

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

export function useParamForm(specs: ParamSpec[]) {
  const schema = buildParamSchema(specs);
  const defaultValues = extractDefaults(specs);

  return useForm({
    resolver: zodResolver(schema),
    defaultValues,
    mode: "onBlur",
  });
}
