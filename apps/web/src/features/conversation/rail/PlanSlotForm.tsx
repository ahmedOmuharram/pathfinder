"use client";

import type {
  PlanSlotForm as SlotForm,
  PlanSlotOption as SlotOption,
} from "@pathfinder/shared";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils/cn";

export type { SlotForm, SlotOption };

export interface SlotAnswerEntry {
  stepId: string;
  paramName: string;
  value: unknown;
}

function slotKey(slot: { stepId: string; paramName: string }): string {
  return `${slot.stepId}:${slot.paramName}`;
}

export function PlanSlotForms({
  slots,
  values,
  onChange,
}: {
  slots: SlotForm[];
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}) {
  if (slots.length === 0) return null;
  return (
    <div
      data-testid="plan-slot-forms"
      className="space-y-3 rounded-md border border-amber-300/40 bg-amber-50/40 p-3 text-xs dark:bg-amber-950/30"
    >
      <div className="text-[11px] font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-200">
        Answer the questions below before approving
      </div>
      {slots.map((slot) => (
        <SlotField
          key={slotKey(slot)}
          slot={slot}
          value={values[slotKey(slot)]}
          onChange={(v) => onChange(slotKey(slot), v)}
        />
      ))}
    </div>
  );
}

function SlotField({
  slot,
  value,
  onChange,
}: {
  slot: SlotForm;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  if (slot.status === "needs_discovery") {
    return (
      <div className="rounded-md border border-border bg-card/60 p-2">
        <div className="font-mono text-[11px] text-foreground">{slot.paramName}</div>
        <div className="mt-1 text-[11px] text-muted-foreground">
          Discovery has not enumerated this parameter&apos;s vocabulary. The agent must
          route back to discovery; you cannot fill it from this form.
        </div>
      </div>
    );
  }
  return (
    <div
      data-testid={`slot-field-${slot.stepId}-${slot.paramName}`}
      className="rounded-md border border-border bg-card/80 p-2"
    >
      <label className="block">
        <span className="font-mono text-[11px] text-foreground">
          {slot.paramName}
          {slot.required === true && (
            <span className="ml-1 text-red-500" aria-hidden>
              *
            </span>
          )}
        </span>
        <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">
          {slot.question}
        </p>
        {slot.context !== undefined && slot.context !== "" && (
          <p className="mt-0.5 text-[10px] italic text-muted-foreground/80">
            {slot.context}
          </p>
        )}
        <div className="mt-1.5">
          {slot.options && slot.options.length > 0 ? (
            <SlotOptionPicker
              options={slot.options}
              value={value}
              onChange={onChange}
              testId={`slot-options-${slot.stepId}-${slot.paramName}`}
            />
          ) : (
            <SlotFreeInput
              paramType={slot.paramType}
              value={value}
              onChange={onChange}
              testId={`slot-input-${slot.stepId}-${slot.paramName}`}
            />
          )}
        </div>
      </label>
    </div>
  );
}

function SlotOptionPicker({
  options,
  value,
  onChange,
  testId,
}: {
  options: SlotOption[];
  value: unknown;
  onChange: (v: unknown) => void;
  testId: string;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const selected = options.find((o) => o.value === value);
  return (
    <div data-testid={testId} className="space-y-1">
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="w-full justify-between font-mono text-[11px]"
        onClick={() => setPickerOpen((p) => !p)}
      >
        <span>{selected ? selected.label : "Select an option…"}</span>
        <span className="text-muted-foreground">▾</span>
      </Button>
      {pickerOpen && (
        <ul className="space-y-1 rounded-md border border-border bg-popover p-1">
          {options.map((opt) => (
            <li key={String(opt.label)}>
              <button
                type="button"
                onClick={() => {
                  onChange(opt.value);
                  setPickerOpen(false);
                }}
                className={cn(
                  "flex w-full flex-col gap-0.5 rounded px-2 py-1 text-left hover:bg-muted",
                  selected?.label === opt.label && "bg-muted",
                )}
                data-testid={`slot-option-${opt.label}`}
              >
                <span className="flex items-center gap-1 font-mono text-[11px]">
                  {opt.label}
                  {opt.recommended === true && (
                    <span className="rounded bg-emerald-100 px-1 text-[9px] uppercase tracking-wide text-emerald-700 dark:bg-emerald-900 dark:text-emerald-200">
                      recommended
                    </span>
                  )}
                </span>
                {opt.description !== undefined && opt.description !== "" && (
                  <span className="text-[10px] text-muted-foreground">
                    {opt.description}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SlotFreeInput({
  paramType,
  value,
  onChange,
  testId,
}: {
  paramType: string;
  value: unknown;
  onChange: (v: unknown) => void;
  testId: string;
}) {
  const inputType = paramType === "number" ? "number" : "text";
  const stringValue = value === null || value === undefined ? "" : String(value);
  return (
    <Input
      data-testid={testId}
      type={inputType}
      value={stringValue}
      onChange={(e) => {
        const raw = e.target.value;
        if (inputType === "number") {
          if (raw === "") {
            onChange(undefined);
            return;
          }
          const parsed = Number(raw);
          onChange(Number.isNaN(parsed) ? raw : parsed);
          return;
        }
        onChange(raw);
      }}
      className="h-7 font-mono text-[11px]"
    />
  );
}

export function slotsAreFilled(
  slots: SlotForm[],
  values: Record<string, unknown>,
): boolean {
  return slots
    .filter((s) => s.status !== "needs_discovery")
    .every((s) => {
      const v = values[slotKey(s)];
      return v !== undefined && v !== null && v !== "";
    });
}

export function buildSlotAnswers(
  slots: SlotForm[],
  values: Record<string, unknown>,
): SlotAnswerEntry[] {
  return slots
    .filter((s) => s.status !== "needs_discovery")
    .map((s) => ({
      stepId: s.stepId,
      paramName: s.paramName,
      value: values[slotKey(s)],
    }))
    .filter((a) => a.value !== undefined && a.value !== null && a.value !== "");
}
