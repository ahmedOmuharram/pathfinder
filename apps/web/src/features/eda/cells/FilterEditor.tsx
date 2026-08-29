"use client";

import { useState } from "react";
import type { EdaFilter } from "@pathfinder/shared/generated/types/EdaFilter";
import type { EdaVariableResponse } from "@pathfinder/shared/generated/types/EdaVariableResponse";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";

import {
  draftToFilter,
  editableFilterType,
  isDraftApplicable,
  type FilterDraft,
} from "../filterDrafts";

const READ_ONLY_NOTE = "Set membership and multi-filters are available through chat.";
const MULTIVALUED_NOTE =
  "one record can carry several values, so these counts do not add up to the subset size";

export interface FilterEditorProps {
  variable: EdaVariableResponse;
  current: EdaFilter | null;
  onApply: (filter: EdaFilter) => void;
  onCancel: () => void;
}

function seedValues(current: EdaFilter | null): string[] {
  return current !== null && current.type === "stringSet" ? [...current.stringSet] : [];
}

function seedNumbers(
  variable: EdaVariableResponse,
  current: EdaFilter | null,
): { min: string; max: string } {
  if (current !== null && current.type === "numberRange") {
    return { min: String(current.min), max: String(current.max) };
  }
  return {
    min: variable.rangeMin == null ? "" : String(variable.rangeMin),
    max: variable.rangeMax == null ? "" : String(variable.rangeMax),
  };
}

function seedDates(
  variable: EdaVariableResponse,
  current: EdaFilter | null,
): { min: string; max: string } {
  if (current !== null && current.type === "dateRange") {
    return { min: current.min.slice(0, 10), max: current.max.slice(0, 10) };
  }
  return {
    min: (variable.dateMin ?? "").slice(0, 10),
    max: (variable.dateMax ?? "").slice(0, 10),
  };
}

function initialDraft(
  variable: EdaVariableResponse,
  current: EdaFilter | null,
): FilterDraft | null {
  switch (editableFilterType(variable.filterType)) {
    case "stringSet":
      return { kind: "stringSet", values: seedValues(current) };
    case "numberRange":
      return { kind: "numberRange", ...seedNumbers(variable, current) };
    case "dateRange":
      return { kind: "dateRange", ...seedDates(variable, current) };
    case null:
      return null;
  }
}

export function FilterEditor({
  variable,
  current,
  onApply,
  onCancel,
}: FilterEditorProps) {
  const [draft, setDraft] = useState<FilterDraft | null>(() =>
    initialDraft(variable, current),
  );

  if (draft === null) {
    return (
      <div className="space-y-2">
        <p data-testid="eda-filter-read-only" className="text-xs text-muted-foreground">
          {READ_ONLY_NOTE}
        </p>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium">{variable.displayName}</p>
      {draft.kind === "stringSet" ? (
        <VocabularyList
          vocabulary={variable.vocabulary}
          checked={draft.values}
          onToggle={(values) => setDraft({ kind: "stringSet", values })}
        />
      ) : (
        <BoundsPair
          kind={draft.kind}
          min={draft.min}
          max={draft.max}
          onChange={(next) => setDraft({ ...draft, ...next })}
        />
      )}
      {variable.isMultiValued ? (
        <p
          data-testid="eda-filter-multivalued-note"
          className="text-[11px] text-muted-foreground"
        >
          {MULTIVALUED_NOTE}
        </p>
      ) : null}
      <p className="text-[11px] text-muted-foreground">{READ_ONLY_NOTE}</p>
      <div className="flex justify-end gap-2">
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="button"
          size="sm"
          disabled={!isDraftApplicable(draft)}
          onClick={() =>
            onApply(draftToFilter(variable.entityId, variable.variableId, draft))
          }
        >
          Apply filter
        </Button>
      </div>
    </div>
  );
}

function VocabularyList({
  vocabulary,
  checked,
  onToggle,
}: {
  vocabulary: readonly string[];
  checked: readonly string[];
  onToggle: (values: string[]) => void;
}) {
  return (
    <ul className="max-h-48 space-y-1 overflow-y-auto">
      {vocabulary.map((value) => (
        <li key={value} className="flex items-center gap-2">
          <Checkbox
            aria-label={value}
            checked={checked.includes(value)}
            onCheckedChange={() =>
              onToggle(
                checked.includes(value)
                  ? vocabulary.filter((v) => v !== value && checked.includes(v))
                  : vocabulary.filter((v) => v === value || checked.includes(v)),
              )
            }
          />
          <span className="text-xs">{value}</span>
        </li>
      ))}
    </ul>
  );
}

function BoundsPair({
  kind,
  min,
  max,
  onChange,
}: {
  kind: "numberRange" | "dateRange";
  min: string;
  max: string;
  onChange: (next: { min: string } | { max: string }) => void;
}) {
  const type = kind === "numberRange" ? "number" : "date";
  return (
    <div className="flex items-center gap-2">
      <Input
        type={type}
        aria-label="Minimum"
        value={min}
        onChange={(event) => onChange({ min: event.target.value })}
      />
      <span className="text-xs text-muted-foreground">to</span>
      <Input
        type={type}
        aria-label="Maximum"
        value={max}
        onChange={(event) => onChange({ max: event.target.value })}
      />
    </div>
  );
}
