import { Controller, useFormContext, useWatch } from "react-hook-form";
import { Input } from "@/lib/components/ui/Input";
import type { ColocationFormValues } from "../schema/colocationSchema";

// ── Toggle button group ─────────────────────────────────────────────────

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

// ── Offset row (anchor + direction + offset number via Controller) ──────

export function OffsetRow({
  label,
  anchorField,
  directionField,
  offsetField,
}: {
  label: string;
  anchorField: keyof ColocationFormValues;
  directionField: keyof ColocationFormValues;
  offsetField: keyof ColocationFormValues;
}) {
  const { control } = useFormContext<ColocationFormValues>();

  return (
    <div className="space-y-1">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="flex items-center gap-1">
        <Controller
          name={anchorField}
          control={control}
          render={({ field }) => (
            <ToggleGroup
              options={[
                { value: "start" as const, label: "Start" },
                { value: "stop" as const, label: "Stop" },
              ]}
              value={field.value as "start" | "stop"}
              onChange={field.onChange}
              columns={2}
            />
          )}
        />
        <Controller
          name={directionField}
          control={control}
          render={({ field }) => (
            <ToggleGroup
              options={[
                { value: "+" as const, label: "+" },
                { value: "-" as const, label: "\u2212" },
              ]}
              value={field.value as "+" | "-"}
              onChange={field.onChange}
              columns={2}
            />
          )}
        />
        <Controller
          name={offsetField}
          control={control}
          render={({ field }) => (
            <Input
              type="number"
              min={0}
              value={field.value as number}
              onChange={(e) => field.onChange(Math.max(0, Number(e.target.value || 0)))}
              onBlur={field.onBlur}
              ref={field.ref}
              className="h-7 w-20 bg-card text-xs"
            />
          )}
        />
      </div>
    </div>
  );
}

// ── Region editor (region type + begin/end offset rows) ─────────────────

type RegionSuffix = "A" | "B";

export function RegionEditor({
  label,
  suffix,
}: {
  label: string;
  suffix: RegionSuffix;
}) {
  const { control, setValue } = useFormContext<ColocationFormValues>();
  const regionKey = `region${suffix}` as const;
  const beginKey = `begin${suffix}` as const;
  const beginDirKey = `beginDirection${suffix}` as const;
  const beginOffKey = `beginOffset${suffix}` as const;
  const endKey = `end${suffix}` as const;
  const endDirKey = `endDirection${suffix}` as const;
  const endOffKey = `endOffset${suffix}` as const;

  const region = useWatch({ control, name: regionKey });
  const showDetails = region !== "exact";

  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <Controller
        name={regionKey}
        control={control}
        render={({ field }) => (
          <ToggleGroup
            options={[
              { value: "exact" as const, label: "Exact" },
              { value: "upstream" as const, label: "Upstream" },
              { value: "downstream" as const, label: "Downstream" },
              { value: "custom" as const, label: "Custom" },
            ]}
            value={field.value}
            onChange={(r) => {
              field.onChange(r);
              if (r === "exact") {
                setValue(beginKey, "start");
                setValue(beginDirKey, "+");
                setValue(beginOffKey, 0);
                setValue(endKey, "stop");
                setValue(endDirKey, "+");
                setValue(endOffKey, 0);
              } else if (r === "upstream") {
                setValue(beginKey, "start");
                setValue(beginDirKey, "-");
                setValue(beginOffKey, 0);
                setValue(endKey, "start");
                setValue(endDirKey, "+");
                setValue(endOffKey, 0);
              } else if (r === "downstream") {
                setValue(beginKey, "stop");
                setValue(beginDirKey, "-");
                setValue(beginOffKey, 0);
                setValue(endKey, "stop");
                setValue(endDirKey, "+");
                setValue(endOffKey, 0);
              }
            }}
            columns={4}
          />
        )}
      />
      {showDetails && (
        <div className="grid grid-cols-2 gap-3 rounded-md border border-border bg-background p-2">
          <OffsetRow
            label="Begin"
            anchorField={beginKey}
            directionField={beginDirKey}
            offsetField={beginOffKey}
          />
          <OffsetRow
            label="End"
            anchorField={endKey}
            directionField={endDirKey}
            offsetField={endOffKey}
          />
        </div>
      )}
    </div>
  );
}
