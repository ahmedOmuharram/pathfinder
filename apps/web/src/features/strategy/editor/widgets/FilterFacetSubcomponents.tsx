"use client";

import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import type { FilterEntry } from "./filterParamLogic";
import type { OntologyTerm } from "./ontologyTypes";

export interface FacetEditorProps {
  term: OntologyTerm;
  current: FilterEntry | null;
  onChange: (next: FilterEntry | null) => void;
}

export function NumericRangeFacet({
  term,
  current,
  onChange,
}: FacetEditorProps) {
  const minBound = inferNumericBound(term.values, "min") ?? 0;
  const maxBound = inferNumericBound(term.values, "max") ?? 100;
  const value = readRangeValue(current);
  const step = term.precision != null ? Math.pow(10, -term.precision) : 1;

  const sliderValue: [number, number] = [
    typeof value.min === "number" ? value.min : minBound,
    typeof value.max === "number" ? value.max : maxBound,
  ];

  const commit = (low: number, high: number) => {
    onChange({
      field: term.term,
      type: "number",
      isRange: true,
      value: { min: low, max: high },
    });
  };

  return (
    <div className="space-y-2 pt-1">
      <Slider
        value={sliderValue}
        min={minBound}
        max={maxBound}
        step={step}
        onValueChange={(next) => {
          const [low, high] = next;
          if (low === undefined || high === undefined) return;
          commit(low, high);
        }}
        aria-label={`${term.display ?? term.term} range`}
      />
      <div className="flex items-center gap-2">
        <Input
          type="number"
          aria-label={`${term.term} min`}
          value={String(sliderValue[0])}
          onChange={(e) => commit(Number(e.target.value), sliderValue[1])}
          className="h-8 w-24"
        />
        <span className="text-xs text-muted-foreground">to</span>
        <Input
          type="number"
          aria-label={`${term.term} max`}
          value={String(sliderValue[1])}
          onChange={(e) => commit(sliderValue[0], Number(e.target.value))}
          className="h-8 w-24"
        />
      </div>
    </div>
  );
}

export function DateRangeFacet({ term, current, onChange }: FacetEditorProps) {
  const value = readRangeValue(current);
  return (
    <div className="flex items-center gap-2">
      <Input
        type="date"
        aria-label={`${term.term} from`}
        value={typeof value.min === "string" ? value.min : ""}
        onChange={(e) =>
          onChange({
            field: term.term,
            type: "date",
            isRange: true,
            value: { min: e.target.value, max: value.max ?? null },
          })
        }
        className="h-8 w-40"
      />
      <span className="text-xs text-muted-foreground">to</span>
      <Input
        type="date"
        aria-label={`${term.term} to`}
        value={typeof value.max === "string" ? value.max : ""}
        onChange={(e) =>
          onChange({
            field: term.term,
            type: "date",
            isRange: true,
            value: { min: value.min ?? null, max: e.target.value },
          })
        }
        className="h-8 w-40"
      />
    </div>
  );
}

export function MultiPickFacet({ term, current, onChange }: FacetEditorProps) {
  const options: ComboboxOption[] = (term.values ?? [])
    .filter((v): v is string => typeof v === "string")
    .map((v) => ({ value: v, label: v }));
  const selected = Array.isArray(current?.value)
    ? current.value.filter((v): v is string => typeof v === "string")
    : [];

  return (
    <Combobox
      multiple
      options={options}
      value={selected}
      onChange={(next) => {
        if (next.length === 0) {
          onChange(null);
          return;
        }
        onChange({ field: term.term, type: "string", value: next });
      }}
      placeholder={`Select ${term.display ?? term.term}…`}
      emptyMessage="No values"
    />
  );
}

export function StringFacet({ term, current, onChange }: FacetEditorProps) {
  const text = typeof current?.value === "string" ? current.value : "";
  return (
    <Input
      type="text"
      aria-label={term.display ?? term.term}
      value={text}
      onChange={(e) => {
        const next = e.target.value;
        if (next === "") {
          onChange(null);
          return;
        }
        onChange({ field: term.term, type: "string", value: next });
      }}
      className="h-8"
    />
  );
}

function readRangeValue(current: FilterEntry | null): {
  min: number | string | null | undefined;
  max: number | string | null | undefined;
} {
  if (current === null) return { min: undefined, max: undefined };
  const v = current.value;
  if (v !== null && typeof v === "object" && !Array.isArray(v)) {
    return { min: v.min, max: v.max };
  }
  return { min: undefined, max: undefined };
}

function inferNumericBound(
  values: ReadonlyArray<string | null> | undefined,
  which: "min" | "max",
): number | null {
  if (!values) return null;
  const nums = values
    .map((v) => (v === null ? null : Number(v)))
    .filter((n): n is number => n !== null && !Number.isNaN(n));
  if (nums.length === 0) return null;
  return which === "min" ? Math.min(...nums) : Math.max(...nums);
}
