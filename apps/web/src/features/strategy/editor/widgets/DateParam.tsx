"use client";

import { Input } from "@/components/ui/input";
import type { ParamWidgetProps } from "./types";

function specMin(spec: ParamWidgetProps["spec"]): string | undefined {
  if (typeof spec.min === "number") return String(spec.min);
  return undefined;
}
function specMax(spec: ParamWidgetProps["spec"]): string | undefined {
  if (typeof spec.max === "number") return String(spec.max);
  return undefined;
}

export function DateParam({ spec, name, field }: ParamWidgetProps) {
  const errors = field.state.meta.errors;
  const hasError = errors.length > 0;
  const errorMessage = hasError ? String(errors[0]) : null;

  return (
    <div>
      <Input
        name={name}
        type="date"
        aria-label="date input"
        value={typeof field.state.value === "string" ? field.state.value : ""}
        onChange={(event) => field.handleChange(event.target.value)}
        onBlur={field.handleBlur}
        min={specMin(spec)}
        max={specMax(spec)}
        aria-invalid={hasError ? "true" : undefined}
        aria-describedby={hasError ? `${name}-error` : undefined}
        aria-required={spec.allowEmptyValue === false ? "true" : undefined}
      />
      {hasError && errorMessage != null && (
        <p id={`${name}-error`} role="alert" className="mt-1 text-xs text-destructive">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
