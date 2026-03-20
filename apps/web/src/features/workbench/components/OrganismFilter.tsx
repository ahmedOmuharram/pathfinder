"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Loader2, X } from "lucide-react";

interface OrganismFilterProps {
  organisms: string[];
  selectedOrganism: string | null;
  onSelect: (organism: string | null) => void;
  organismFilter: string;
  onFilterChange: (filter: string) => void;
  filteredOrganisms: string[];
}

export function OrganismFilter({
  organisms,
  selectedOrganism,
  onSelect,
  organismFilter,
  onFilterChange,
  filteredOrganisms,
}: OrganismFilterProps) {
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  if (organisms.length === 0) {
    return (
      <div className="flex h-7 items-center rounded-md border border-input bg-background px-2.5 text-xs text-muted-foreground">
        <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
        Loading organisms...
      </div>
    );
  }

  return (
    <div ref={dropdownRef} className="relative">
      {selectedOrganism != null && selectedOrganism !== "" ? (
        <div className="flex h-7 w-full items-center justify-between rounded-md border border-input bg-background px-2.5 text-xs text-foreground">
          <span className="truncate italic">{selectedOrganism}</span>
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="ml-1 shrink-0 rounded p-0.5 hover:bg-accent"
          >
            <X className="h-3 w-3 text-muted-foreground" />
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => {
            setOpen(!open);
            onFilterChange("");
            setTimeout(() => inputRef.current?.focus(), 0);
          }}
          className="flex h-7 w-full items-center justify-between rounded-md border border-input bg-background px-2.5 text-xs text-foreground"
        >
          <span className="truncate text-muted-foreground">Filter by organism...</span>
          <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        </button>
      )}

      {open && (
        <div className="absolute left-0 right-0 top-full z-20 mt-1 rounded-md border border-border bg-popover shadow-md">
          <div className="border-b border-border p-1.5">
            <input
              ref={inputRef}
              type="text"
              value={organismFilter}
              onChange={(e) => onFilterChange(e.target.value)}
              placeholder="Search organisms..."
              className="h-6 w-full rounded border-none bg-transparent px-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === "Escape") setOpen(false);
              }}
            />
          </div>
          <div className="max-h-48 overflow-y-auto">
            {filteredOrganisms.map((org) => (
              <button
                key={org}
                type="button"
                onClick={() => {
                  onSelect(org);
                  setOpen(false);
                  onFilterChange("");
                }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-xs hover:bg-accent"
              >
                <span className="truncate italic">{org}</span>
              </button>
            ))}
            {filteredOrganisms.length === 0 && (
              <p className="px-3 py-2 text-[10px] text-muted-foreground">
                No organisms match.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
