import { useRef } from "react";
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
  const cacheRef = useRef<{
    signature: string;
    schema: ReturnType<typeof buildParamSchema>;
    defaultValues: Record<string, string | string[]>;
  } | null>(null);
  const signature = JSON.stringify(specs);

  if (cacheRef.current == null || cacheRef.current.signature !== signature) {
    cacheRef.current = {
      signature,
      schema: buildParamSchema(specs),
      defaultValues: extractDefaults(specs),
    };
  }

  const { schema, defaultValues } = cacheRef.current;

  return useForm({
    resolver: zodResolver(schema),
    defaultValues,
    values: defaultValues,
    mode: "onBlur",
  });
}
