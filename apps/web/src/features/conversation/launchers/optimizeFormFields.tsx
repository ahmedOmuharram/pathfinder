"use client";

import { useStore } from "@tanstack/react-form";
import type { ReactNode } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";

import type { LauncherForm, ModelOption, StepLite } from "./optimizeFormTypes";

export { ParamPicker } from "./ParamPicker";

const DEFAULT_BUDGET = 20;

function FieldShell({
  label,
  children,
}: {
  label: ReactNode;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}

export function StepPicker({
  form,
  steps,
}: {
  form: LauncherForm;
  steps: StepLite[];
}) {
  const value = useStore(form.store, (s) => s.values.stepId);
  return (
    <FieldShell label="Step">
      <Select
        value={value === null ? "" : String(value)}
        onValueChange={(v) =>
          form.setStepId(v === "" ? null : Number(v))
        }
      >
        <SelectTrigger data-testid="optimize-step-trigger">
          <SelectValue placeholder="Pick a step" />
        </SelectTrigger>
        <SelectContent>
          {steps.map((s) => (
            <SelectItem key={s.id} value={String(s.id)}>
              {s.displayName ?? s.searchName ?? s.id}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </FieldShell>
  );
}

export function CriterionField({ form }: { form: LauncherForm }) {
  const value = useStore(form.store, (s) => s.values.criterion);
  return (
    <FieldShell label="Criterion">
      <Textarea
        rows={3}
        placeholder='e.g. "match the gold gene set" or "find params giving 50–200 results"'
        value={value}
        onChange={(e) => form.setCriterion(e.target.value)}
        data-testid="optimize-criterion-input"
      />
    </FieldShell>
  );
}

export function BudgetField({ form }: { form: LauncherForm }) {
  const value = useStore(form.store, (s) => s.values.budget);
  return (
    <FieldShell label={`Budget · ${value} trials`}>
      <Slider
        min={1}
        max={100}
        step={1}
        value={[value]}
        onValueChange={(v) => form.setBudget(v[0] ?? DEFAULT_BUDGET)}
        data-testid="optimize-budget-slider"
      />
    </FieldShell>
  );
}

export function ModelField({
  form,
  options,
}: {
  form: LauncherForm;
  options: ModelOption[];
}) {
  const value = useStore(form.store, (s) => s.values.modelId);
  return (
    <FieldShell label="Model (optional)">
      <Select
        value={value}
        onValueChange={(v) => form.setModelId(v)}
      >
        <SelectTrigger data-testid="optimize-model-trigger">
          <SelectValue placeholder="System default" />
        </SelectTrigger>
        <SelectContent>
          {options.map((m) => (
            <SelectItem key={m.id} value={m.id}>
              {m.name ?? m.id}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </FieldShell>
  );
}
