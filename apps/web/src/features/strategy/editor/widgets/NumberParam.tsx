"use client";

import { Input } from "@/components/ui/input";
import type { ParamWidgetProps } from "./types";

export function NumberParam({ spec, name, field }: ParamWidgetProps) {
  const errors = field.state.meta.errors;
  const hasError = errors.length > 0;
  const errorMessage = hasError ? String(errors[0]) : null;

  return (
    <div>
      <Input
        name={name}
        type="number"
        value={typeof field.state.value === "string" ? field.state.value : ""}
        onChange={(event) => field.handleChange(event.target.value)}
        onBlur={field.handleBlur}
        min={spec.min ?? undefined}
        max={spec.max ?? undefined}
        step={spec.increment ?? undefined}
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
