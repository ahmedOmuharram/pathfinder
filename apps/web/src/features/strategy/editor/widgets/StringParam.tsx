"use client";

import { Input } from "@/components/ui/input";
import type { ParamWidgetProps } from "./types";

export function StringParam({ spec, name, field }: ParamWidgetProps) {
  const isNumeric =
    spec.isNumber === true ||
    ["number", "integer", "float"].includes(spec.type.toLowerCase());

  const errors = field.state.meta.errors;
  const hasError = errors.length > 0;
  const errorMessage = hasError ? String(errors[0]) : null;

  return (
    <div>
      <Input
        name={name}
        value={typeof field.state.value === "string" ? field.state.value : ""}
        onChange={(event) => field.handleChange(event.target.value)}
        onBlur={field.handleBlur}
        type={isNumeric ? "number" : "text"}
        min={isNumeric && spec.min != null ? spec.min : undefined}
        max={isNumeric && spec.max != null ? spec.max : undefined}
        step={isNumeric && spec.increment != null ? spec.increment : undefined}
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
