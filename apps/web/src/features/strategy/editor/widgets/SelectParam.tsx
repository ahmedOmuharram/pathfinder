import { cn } from "@/lib/utils/cn";
import { isMultiParam } from "@/features/strategy/parameters/spec";
import type { ParamWidgetProps } from "./types";

export function SelectParam({ spec, name, options, field }: ParamWidgetProps) {
  const multi = isMultiParam(spec);
  const errors = field.state.meta.errors;
  const hasError = errors.length > 0;
  const errorMessage = hasError ? String(errors[0]) : null;

  if (!multi) {
    return (
      <div>
        <select
          value={field.state.value as string}
          onChange={(e) => field.handleChange(e.target.value)}
          onBlur={field.handleBlur}
          aria-invalid={hasError ? "true" : undefined}
          aria-describedby={hasError ? `${name}-error` : undefined}
          className={cn(
            "w-full rounded-md border px-2 py-1.5 text-sm bg-card text-foreground",
            hasError ? "border-destructive/30 bg-destructive/5" : "border-border",
          )}
        >
          {spec.allowEmptyValue !== false && (
            <option value="">-- Select --</option>
          )}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {hasError && errorMessage != null && (
          <p id={`${name}-error`} role="alert" className="mt-1 text-xs text-destructive">
            {errorMessage}
          </p>
        )}
      </div>
    );
  }

  const selected: string[] = Array.isArray(field.state.value)
    ? field.state.value
    : [];
  const allSelected = options.length > 0 && selected.length === options.length;

  const toggleAll = () => {
    field.handleChange(allSelected ? [] : options.map((o) => o.value));
  };

  const toggle = (val: string) => {
    field.handleChange(
      selected.includes(val)
        ? selected.filter((v) => v !== val)
        : [...selected, val],
    );
  };

  return (
    <div>
      <div
        aria-invalid={hasError ? "true" : undefined}
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
              checked={selected.includes(opt.value)}
              onChange={() => toggle(opt.value)}
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
