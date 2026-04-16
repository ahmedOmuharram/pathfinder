"use client";

import { useStore } from "@tanstack/react-form";
import { Card } from "@/lib/components/ui/Card";
import type { ColocationFormValues } from "../schema/colocationSchema";
import { useColocationForm, type ColocationForm } from "../hooks/useColocationForm";
import { ToggleGroup, RegionEditor } from "./ColocationWidgets";

export const DEFAULT_COLOCATION: ColocationFormValues = {
  operation: "overlaps",
  strand: "either strand",
  output: "a",
  regionA: "exact",
  beginA: "start",
  beginDirectionA: "+",
  beginOffsetA: 0,
  endA: "stop",
  endDirectionA: "+",
  endOffsetA: 0,
  regionB: "exact",
  beginB: "start",
  beginDirectionB: "+",
  beginOffsetB: 0,
  endB: "stop",
  endDirectionB: "+",
  endOffsetB: 0,
};

export function resolveParams(params: Partial<ColocationFormValues> | null | undefined): ColocationFormValues {
  return { ...DEFAULT_COLOCATION, ...params };
}

function ColocationChangeSync({
  form,
  onChange,
}: {
  form: ColocationForm;
  onChange: (values: ColocationFormValues) => void;
}) {
  const values = useStore(form.store, (s) => s.values);
  queueMicrotask(() => onChange(values));
  return null;
}

export function ColocationEditor({
  initialValues,
  onChange,
}: {
  initialValues?: Partial<ColocationFormValues>;
  onChange?: (values: ColocationFormValues) => void;
}) {
  const form = useColocationForm(initialValues);

  return (
    <>
      {onChange != null && <ColocationChangeSync form={form} onChange={onChange} />}
      <Card className="mt-3 space-y-3 rounded-md p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Colocation parameters
        </div>

        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">Operation</div>
          <form.Field name="operation">
            {(field) => (
              <ToggleGroup
                options={[
                  { value: "overlaps" as const, label: "Overlaps" },
                  { value: "contains" as const, label: "Contains" },
                  { value: "is contained in" as const, label: "Is contained in" },
                ]}
                value={field.state.value as string}
                onChange={(v) => field.handleChange(v as ColocationFormValues["operation"])}
              />
            )}
          </form.Field>
        </div>

        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">Strand</div>
          <form.Field name="strand">
            {(field) => (
              <ToggleGroup
                options={[
                  { value: "either strand" as const, label: "Either" },
                  { value: "same strand" as const, label: "Same" },
                  { value: "opposite strand" as const, label: "Opposite" },
                ]}
                value={field.state.value as string}
                onChange={(v) => field.handleChange(v as ColocationFormValues["strand"])}
              />
            )}
          </form.Field>
        </div>

        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">Output</div>
          <form.Field name="output">
            {(field) => (
              <ToggleGroup
                options={[
                  { value: "a" as const, label: "Step A" },
                  { value: "b" as const, label: "Step B" },
                ]}
                value={field.state.value as string}
                onChange={(v) => field.handleChange(v as ColocationFormValues["output"])}
                columns={2}
              />
            )}
          </form.Field>
        </div>

        <RegionEditor label="Region A" suffix="A" form={form} />
        <RegionEditor label="Region B" suffix="B" form={form} />
      </Card>
    </>
  );
}
