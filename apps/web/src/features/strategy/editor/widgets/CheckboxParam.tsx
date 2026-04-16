import { cn } from "@/lib/utils/cn";
import { isMultiParam } from "@/features/strategy/parameters/spec";
import type { ParamWidgetProps } from "./types";

export function CheckboxParam({ spec, name, options, field }: ParamWidgetProps) {
  const multi = isMultiParam(spec);
  const errors = field.state.meta.errors;
  const hasError = errors.length > 0;
  const errorMessage = hasError ? String(errors[0]) : null;

  if (!multi) {
    return (
      <div>
        <div
          role="radiogroup"
          aria-invalid={hasError ? "true" : undefined}
          aria-describedby={hasError ? `${name}-error` : undefined}
          className={cn(
            "rounded-md border bg-card p-2 space-y-1",
            hasError ? "border-destructive/30 bg-destructive/5" : "border-border",
          )}
        >
          {options.map((opt) => (
            <label key={opt.value} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name={name}
                value={opt.value}
                checked={field.state.value === opt.value}
                onChange={() => field.handleChange(opt.value)}
                onBlur={field.handleBlur}
                className="accent-primary"
              />
              {opt.label}
            </label>
          ))}
        </div>
        {hasError && errorMessage != null && (
          <p id={`${name}-error`} role="alert" className="mt-1 text-xs text-destructive">
            {errorMessage}
          </p>
        )}
      </div>
    );
  }

  const currentValue: string[] = Array.isArray(field.state.value)
    ? (field.state.value as unknown[]).filter(
        (v): v is string => typeof v === "string",
      )
    : [];
  const allSelected = options.length > 0 && currentValue.length === options.length;

  const toggleAll = () => {
    field.handleChange(allSelected ? [] : options.map((o) => o.value));
  };

  const toggle = (val: string) => {
    field.handleChange(
      currentValue.includes(val)
        ? currentValue.filter((v) => v !== val)
        : [...currentValue, val],
    );
  };

  return (
    <div>
      <fieldset
        aria-invalid={hasError ? "true" : undefined}
        aria-describedby={hasError ? `${name}-error` : undefined}
        className={cn(
          "rounded-md border bg-card max-h-48 overflow-y-auto p-2",
          hasError ? "border-destructive/30 bg-destructive/5" : "border-border",
        )}
      >
        {options.length > 3 && (
          <label className="flex items-center gap-2 text-xs text-muted-foreground mb-1 pb-1 border-b border-border">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="accent-primary"
            />
            Select all ({options.length})
          </label>
        )}
        {options.map((opt) => (
          <label key={opt.value} className="flex items-center gap-2 text-sm py-0.5">
            <input
              type="checkbox"
              checked={currentValue.includes(opt.value)}
              onChange={() => toggle(opt.value)}
              onBlur={field.handleBlur}
              className="accent-primary"
            />
            {opt.label}
          </label>
        ))}
      </fieldset>
      {hasError && errorMessage != null && (
        <p id={`${name}-error`} role="alert" className="mt-1 text-xs text-destructive">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
