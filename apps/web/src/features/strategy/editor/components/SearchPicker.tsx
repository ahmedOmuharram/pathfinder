"use client";

import type { Search } from "@pathfinder/shared";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";

interface SearchPickerProps {
  searches: Search[];
  value: string | null;
  /** Called with the picked search name (null when cleared). */
  onChange: (nextSearchName: string | null) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function SearchPicker({
  searches,
  value,
  onChange,
  placeholder = "Pick a search…",
  disabled,
}: SearchPickerProps) {
  const options: ComboboxOption[] = searches.map((s) => ({
    value: s.name,
    label: s.displayName || s.name,
  }));

  const recordTypeByName = new Map(searches.map((s) => [s.name, s.recordType]));

  return (
    <Combobox
      options={options}
      value={value}
      onChange={(next) => onChange(next)}
      placeholder={placeholder}
      groupBy={(option) => recordTypeByName.get(option.value) ?? "other"}
      emptyMessage="No matching searches"
      {...(disabled !== undefined && { disabled })}
    />
  );
}

export type { Search } from "@pathfinder/shared";
