"use client";

import { useRef, useState } from "react";
import { useOnClickOutside } from "usehooks-ts";
import { Check, ChevronDown, Loader2, X } from "lucide-react";

interface Option {
  value: string;
  label: string;
}

interface SearchableMultiSelectProps {
  options: Option[];
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  loading?: boolean;
  disabled?: boolean;
  maxHeight?: string;
}

export function SearchableMultiSelect({
  options,
  selected,
  onChange,
  placeholder = "Select...",
  searchPlaceholder = "Search...",
  loading = false,
  disabled = false,
  maxHeight = "max-h-48",
}: SearchableMultiSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useOnClickOutside(dropdownRef as React.RefObject<HTMLElement>, () =>
    setOpen(false),
  );

  const filteredOptions = options.filter((opt) =>
    opt.label.toLowerCase().includes(search.toLowerCase()),
  );

  const selectedOptions = options.filter((opt) => selected.includes(opt.value));

  const toggleOption = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  const removeOption = (value: string) => {
    onChange(selected.filter((v) => v !== value));
  };

  const openDropdown = () => {
    if (disabled) return;
    setOpen(!open);
    setSearch("");
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  if (loading) {
    return (
      <div className="flex h-7 items-center rounded-md border border-input bg-background px-2.5 text-xs text-muted-foreground">
        <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
        Loading...
      </div>
    );
  }

  return (
    <div ref={dropdownRef} className="relative">
      {/* When dropdown is closed and items are selected, show chips */}
      {!open && selectedOptions.length > 0 && (
        <div className="flex min-h-7 flex-wrap items-center gap-1 rounded-md border border-input bg-background px-2 py-1">
          {selectedOptions.map((opt) => (
            <span
              key={opt.value}
              className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs"
            >
              {opt.label}
              <button
                type="button"
                aria-label={`Remove ${opt.label}`}
                onClick={(e) => {
                  e.stopPropagation();
                  removeOption(opt.value);
                }}
                disabled={disabled}
                className="rounded p-0.5 hover:bg-accent"
              >
                <X className="h-2.5 w-2.5 text-muted-foreground" />
              </button>
            </span>
          ))}
          <button
            type="button"
            onClick={openDropdown}
            disabled={disabled}
            className="ml-auto shrink-0"
            aria-label="Toggle dropdown"
          >
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          </button>
        </div>
      )}

      {/* When nothing selected or dropdown is open, show trigger button */}
      {(open || selectedOptions.length === 0) && (
        <button
          type="button"
          onClick={openDropdown}
          disabled={disabled}
          className="flex min-h-7 w-full items-center justify-between rounded-md border border-input bg-background px-2.5 py-1 text-xs"
        >
          <span className="truncate text-muted-foreground">
            {selectedOptions.length > 0
              ? `${selectedOptions.length} selected`
              : placeholder}
          </span>
          <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        </button>
      )}

      {/* Dropdown */}
      {open && (
        <div className="absolute left-0 right-0 top-full z-20 mt-1 rounded-md border border-border bg-popover shadow-md">
          <div className="border-b border-border p-1.5">
            <input
              ref={inputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={searchPlaceholder}
              className="h-6 w-full rounded border-none bg-transparent px-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === "Escape") setOpen(false);
              }}
            />
          </div>
          <div className={`${maxHeight} overflow-y-auto`}>
            {filteredOptions.map((opt) => {
              const isSelected = selected.includes(opt.value);
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => toggleOption(opt.value)}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-accent"
                >
                  <span
                    className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-sm border border-input"
                    {...(isSelected ? { "data-checked": true } : {})}
                  >
                    {isSelected && <Check className="h-3 w-3" />}
                  </span>
                  <span className="truncate">{opt.label}</span>
                </button>
              );
            })}
            {filteredOptions.length === 0 && (
              <p className="px-3 py-2 text-[10px] text-muted-foreground">
                No results match.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
