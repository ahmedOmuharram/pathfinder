import { useStore } from "@tanstack/react-form";
import { Input } from "@/lib/components/ui/Input";
import type { ColocationFormValues } from "../schema/colocationSchema";
import type { ColocationForm } from "../hooks/useColocationForm";

type ToggleOption<T extends string> = { value: T; label: string };

export function ToggleGroup<T extends string>({
  options,
  value,
  onChange,
  columns,
}: {
  options: ToggleOption<T>[];
  value: T;
  onChange: (next: T) => void;
  columns?: number;
}) {
  const gridCols =
    columns === 2
      ? "grid-cols-2"
      : columns === 4
        ? "grid-cols-4"
        : "grid-cols-3";
  return (
    <div className={`grid ${gridCols} gap-1`}>
      {options.map((opt) => {
        const selected = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`rounded-md border px-2 py-1.5 text-xs font-semibold transition-colors duration-150 ${
              selected
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card text-foreground hover:border-input"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export function OffsetRow({
  label,
  anchorField,
  directionField,
  offsetField,
  form,
}: {
  label: string;
  anchorField: keyof ColocationFormValues;
  directionField: keyof ColocationFormValues;
  offsetField: keyof ColocationFormValues;
  form: ColocationForm;
}) {
  return (
    <div className="space-y-1">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="flex items-center gap-1">
        <form.Field name={anchorField}>
          {(field) => (
            <ToggleGroup
              options={[
                { value: "start" as const, label: "Start" },
                { value: "stop" as const, label: "Stop" },
              ]}
              value={field.state.value as string}
              onChange={(v) => field.handleChange(v as never)}
              columns={2}
            />
          )}
        </form.Field>
        <form.Field name={directionField}>
          {(field) => (
            <ToggleGroup
              options={[
                { value: "+" as const, label: "+" },
                { value: "-" as const, label: "\u2212" },
              ]}
              value={field.state.value as string}
              onChange={(v) => field.handleChange(v as never)}
              columns={2}
            />
          )}
        </form.Field>
        <form.Field name={offsetField}>
          {(field) => (
            <Input
              type="number"
              min={0}
              value={field.state.value as number}
              onChange={(e) => field.handleChange(Math.max(0, Number(e.target.value || 0)) as never)}
              onBlur={field.handleBlur}
              className="h-7 w-20 bg-card text-xs"
            />
          )}
        </form.Field>
      </div>
    </div>
  );
}

export function RegionEditor({
  label,
  suffix,
  form,
}: {
  label: string;
  suffix: "A" | "B";
  form: ColocationForm;
}) {
  const regionKey = `region${suffix}` as keyof ColocationFormValues;
  const beginKey = `begin${suffix}` as keyof ColocationFormValues;
  const beginDirKey = `beginDirection${suffix}` as keyof ColocationFormValues;
  const beginOffKey = `beginOffset${suffix}` as keyof ColocationFormValues;
  const endKey = `end${suffix}` as keyof ColocationFormValues;
  const endDirKey = `endDirection${suffix}` as keyof ColocationFormValues;
  const endOffKey = `endOffset${suffix}` as keyof ColocationFormValues;

  const region = useStore(form.store, (s) => s.values[regionKey]);
  const showDetails = region !== "exact";

  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <form.Field name={regionKey}>
        {(field) => (
          <ToggleGroup
            options={[
              { value: "exact" as const, label: "Exact" },
              { value: "upstream" as const, label: "Upstream" },
              { value: "downstream" as const, label: "Downstream" },
              { value: "custom" as const, label: "Custom" },
            ]}
            value={field.state.value as string}
            onChange={(r) => {
              field.handleChange(r as never);
              if (r === "exact") {
                form.setFieldValue(beginKey, "start" as never);
                form.setFieldValue(beginDirKey, "+" as never);
                form.setFieldValue(beginOffKey, 0 as never);
                form.setFieldValue(endKey, "stop" as never);
                form.setFieldValue(endDirKey, "+" as never);
                form.setFieldValue(endOffKey, 0 as never);
              } else if (r === "upstream") {
                form.setFieldValue(beginKey, "start" as never);
                form.setFieldValue(beginDirKey, "-" as never);
                form.setFieldValue(beginOffKey, 0 as never);
                form.setFieldValue(endKey, "start" as never);
                form.setFieldValue(endDirKey, "+" as never);
                form.setFieldValue(endOffKey, 0 as never);
              } else if (r === "downstream") {
                form.setFieldValue(beginKey, "stop" as never);
                form.setFieldValue(beginDirKey, "-" as never);
                form.setFieldValue(beginOffKey, 0 as never);
                form.setFieldValue(endKey, "stop" as never);
                form.setFieldValue(endDirKey, "+" as never);
                form.setFieldValue(endOffKey, 0 as never);
              }
            }}
            columns={4}
          />
        )}
      </form.Field>
      {showDetails && (
        <div className="grid grid-cols-2 gap-3 rounded-md border border-border bg-background p-2">
          <OffsetRow label="Begin" anchorField={beginKey} directionField={beginDirKey} offsetField={beginOffKey} form={form} />
          <OffsetRow label="End" anchorField={endKey} directionField={endDirKey} offsetField={endOffKey} form={form} />
        </div>
      )}
    </div>
  );
}
