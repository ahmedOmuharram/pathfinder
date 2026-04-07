import { Controller, useFormContext } from "react-hook-form";
import { cn } from "@/lib/utils/cn";
import { isMultiParam } from "@/features/strategy/parameters/spec";
import type { ParamWidgetProps } from "./types";

export function SelectParam({ spec, name, options }: ParamWidgetProps) {
  const { control } = useFormContext();
  const multi = isMultiParam(spec);

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => {
        const hasError = fieldState.error != null;

        if (!multi) {
          return (
            <div>
              <select
                value={field.value as string}
                onChange={(e) => field.onChange(e.target.value)}
                onBlur={field.onBlur}
                ref={field.ref}
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
              {hasError && fieldState.error?.message != null && (
                <p
                  id={`${name}-error`}
                  role="alert"
                  className="mt-1 text-xs text-destructive"
                >
                  {fieldState.error.message}
                </p>
              )}
            </div>
          );
        }

        const selected: string[] = Array.isArray(field.value)
          ? (field.value as string[])
          : [];
        const allSelected =
          options.length > 0 && selected.length === options.length;

        const toggleAll = () => {
          field.onChange(allSelected ? [] : options.map((o) => o.value));
        };

        const toggle = (val: string) => {
          field.onChange(
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
                hasError
                  ? "border-destructive/30 bg-destructive/5"
                  : "border-border",
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
                <label
                  key={opt.value}
                  className="flex items-center gap-2 text-sm py-0.5"
                >
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
            {hasError && fieldState.error?.message != null && (
              <p
                id={`${name}-error`}
                role="alert"
                className="mt-1 text-xs text-destructive"
              >
                {fieldState.error.message}
              </p>
            )}
          </div>
        );
      }}
    />
  );
}
