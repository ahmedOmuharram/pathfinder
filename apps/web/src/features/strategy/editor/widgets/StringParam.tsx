import { cn } from "@/lib/utils/cn";
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
      <input
        name={name}
        value={(field.state.value as string | undefined) ?? ""}
        onChange={(e) => field.handleChange(e.target.value)}
        onBlur={field.handleBlur}
        type={isNumeric ? "number" : "text"}
        min={isNumeric && spec.min != null ? spec.min : undefined}
        max={isNumeric && spec.max != null ? spec.max : undefined}
        step={isNumeric && spec.increment != null ? spec.increment : undefined}
        aria-invalid={hasError ? "true" : undefined}
        aria-describedby={hasError ? `${name}-error` : undefined}
        aria-required={spec.allowEmptyValue === false ? "true" : undefined}
        className={cn(
          "w-full rounded-md border px-2 py-1.5 text-sm bg-card text-foreground",
          hasError ? "border-destructive/30 bg-destructive/5" : "border-border",
        )}
      />
      {hasError && errorMessage != null && (
        <p id={`${name}-error`} role="alert" className="mt-1 text-xs text-destructive">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
