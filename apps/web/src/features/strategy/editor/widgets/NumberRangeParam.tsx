"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import type { ParamWidgetProps } from "./types";

interface RangeParts {
  min: string;
  max: string;
}

function decode(value: string): RangeParts {
  const idx = value.indexOf("-", 1);
  if (idx <= 0) return { min: value, max: "" };
  return { min: value.slice(0, idx), max: value.slice(idx + 1) };
}

function encode(min: string, max: string): string {
  if (min === "" && max === "") return "";
  return `${min}-${max}`;
}

export function NumberRangeParam({ spec, name, field }: ParamWidgetProps) {
  const initial =
    typeof field.state.value === "string" ? decode(field.state.value) : { min: "", max: "" };
  const [parts, setParts] = useState<RangeParts>(initial);

  const errors = field.state.meta.errors;
  const hasError = errors.length > 0;
  const errorMessage = hasError ? String(errors[0]) : null;

  const update = (next: RangeParts) => {
    setParts(next);
    field.handleChange(encode(next.min, next.max));
  };

  return (
    <div>
      <div className="flex items-center gap-2">
        <Input
          name={`${name}-min`}
          type="number"
          aria-label={`${name} min`}
          value={parts.min}
          onChange={(event) => update({ ...parts, min: event.target.value })}
          onBlur={field.handleBlur}
          min={spec.min ?? undefined}
          max={spec.max ?? undefined}
          step={spec.increment ?? undefined}
          aria-invalid={hasError ? "true" : undefined}
        />
        <span className="text-muted-foreground" aria-hidden>
          —
        </span>
        <Input
          name={`${name}-max`}
          type="number"
          aria-label={`${name} max`}
          value={parts.max}
          onChange={(event) => update({ ...parts, max: event.target.value })}
          onBlur={field.handleBlur}
          min={spec.min ?? undefined}
          max={spec.max ?? undefined}
          step={spec.increment ?? undefined}
          aria-invalid={hasError ? "true" : undefined}
        />
      </div>
      {hasError && errorMessage != null && (
        <p id={`${name}-error`} role="alert" className="mt-1 text-xs text-destructive">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
