"use client";

import { useEffect, useRef } from "react";
import type { ColocationParams } from "@pathfinder/shared";
import { Controller, FormProvider, useFormContext, useWatch } from "react-hook-form";
import { Card } from "@/lib/components/ui/Card";
import type { ColocationFormValues } from "../schema/colocationSchema";
import { useColocationForm } from "../hooks/useColocationForm";
import { ToggleGroup, RegionEditor } from "./ColocationWidgets";

// ── Default colocation params (WDK defaults) ────────────────────────────

export const DEFAULT_COLOCATION: ColocationParams = {
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

export function resolveParams(params: ColocationParams | null | undefined): ColocationParams {
  return { ...DEFAULT_COLOCATION, ...params };
}

// ── Change sync — calls onChange when form values change ─────────────────

function ColocationChangeSync({
  onChange,
}: {
  onChange: (values: ColocationFormValues) => void;
}) {
  const { control } = useFormContext<ColocationFormValues>();
  const values = useWatch({ control });
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    // useWatch can return partial during mount — only fire when fully populated.
    if (values.operation != null) {
      onChangeRef.current(values as ColocationFormValues);
    }
  }, [values]);

  return null;
}

// ── Main colocation editor ──────────────────────────────────────────────

export function ColocationEditor({
  initialValues,
  onChange,
}: {
  initialValues?: Partial<ColocationFormValues>;
  onChange?: (values: ColocationFormValues) => void;
}) {
  const form = useColocationForm(initialValues);
  const { control } = form;

  return (
    <FormProvider {...form}>
      {onChange != null && <ColocationChangeSync onChange={onChange} />}
      <Card className="mt-3 space-y-3 rounded-md p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Colocation parameters
        </div>

        {/* Operation */}
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">Operation</div>
          <Controller
            name="operation"
            control={control}
            render={({ field }) => (
              <ToggleGroup
                options={[
                  { value: "overlaps" as const, label: "Overlaps" },
                  { value: "contains" as const, label: "Contains" },
                  { value: "is contained in" as const, label: "Is contained in" },
                ]}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
        </div>

        {/* Strand */}
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">Strand</div>
          <Controller
            name="strand"
            control={control}
            render={({ field }) => (
              <ToggleGroup
                options={[
                  { value: "either strand" as const, label: "Either" },
                  { value: "same strand" as const, label: "Same" },
                  { value: "opposite strand" as const, label: "Opposite" },
                ]}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
        </div>

        {/* Output */}
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">Output</div>
          <Controller
            name="output"
            control={control}
            render={({ field }) => (
              <ToggleGroup
                options={[
                  { value: "a" as const, label: "Step A" },
                  { value: "b" as const, label: "Step B" },
                ]}
                value={field.value}
                onChange={field.onChange}
                columns={2}
              />
            )}
          />
        </div>

        {/* Region A */}
        <RegionEditor label="Region A" suffix="A" />

        {/* Region B */}
        <RegionEditor label="Region B" suffix="B" />
      </Card>
    </FormProvider>
  );
}
