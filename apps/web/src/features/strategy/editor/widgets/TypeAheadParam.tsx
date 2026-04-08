import { useState, useRef } from "react";
import { useOnClickOutside } from "usehooks-ts";
import { Controller, useFormContext } from "react-hook-form";
import { useDebouncedCallback } from "use-debounce";
import { cn } from "@/lib/utils/cn";
import { isMultiParam } from "@/features/strategy/parameters/spec";
import type { ParamWidgetProps } from "./types";
import type { VocabOption } from "@/lib/utils/vocab";

const MAX_VISIBLE = 50;

export function TypeAheadParam({ spec, name, options }: ParamWidgetProps) {
  const { control } = useFormContext();
  const multi = isMultiParam(spec);

  return (
    <Controller
      name={name}
      control={control}
      render={({ field, fieldState }) => {
        const hasError = fieldState.error != null;
        const errorMessage = fieldState.error?.message;

        const common = {
          onBlur: field.onBlur,
          fieldRef: field.ref,
          name,
          options,
          hasError,
          errorMessage,
        };

        return multi ? (
          <MultiTypeAhead
            {...common}
            value={Array.isArray(field.value) ? (field.value as string[]) : []}
            onChange={(v) => field.onChange(v)}
          />
        ) : (
          <SingleTypeAhead
            {...common}
            value={(field.value ?? "") as string}
            onChange={(v) => field.onChange(v)}
          />
        );
      }}
    />
  );
}


type BaseInnerProps = {
  onBlur: () => void;
  fieldRef: React.RefCallback<HTMLElement>;
  name: string;
  options: VocabOption[];
  hasError: boolean;
  errorMessage: string | undefined;
};

type SingleInnerProps = BaseInnerProps & {
  value: string;
  onChange: (v: string) => void;
};

type MultiInnerProps = BaseInnerProps & {
  value: string[];
  onChange: (v: string[]) => void;
};

function SingleTypeAhead({
  value,
  onChange,
  onBlur,
  fieldRef,
  name,
  options,
  hasError,
  errorMessage,
}: SingleInnerProps) {
  const resolveLabel = (v: string) =>
    v ? (options.find((o) => o.value === v)?.label ?? v) : "";

  const [searchTerm, setSearchTerm] = useState(resolveLabel(value));
  const [filtered, setFiltered] = useState<VocabOption[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const [prevValue, setPrevValue] = useState(value);
  if (value !== prevValue) {
    setPrevValue(value);
    const label = resolveLabel(value);
    if (label !== searchTerm) setSearchTerm(label);
  }

  const doFilter = useDebouncedCallback((term: string) => {
    if (!term.trim()) { setFiltered([]); setIsOpen(false); return; }
    const lower = term.toLowerCase();
    setFiltered(options.filter((o) => o.label.toLowerCase().includes(lower)));
    setIsOpen(true);
  }, 200);

  const close = () => { setIsOpen(false); setFiltered([]); };
  useOnClickOutside(containerRef as React.RefObject<HTMLElement>, close);

  return (
    <div ref={containerRef} className="relative">
      <input
        type="text"
        value={searchTerm}
        onChange={(e) => { setSearchTerm(e.target.value); doFilter(e.target.value); }}
        onKeyDown={(e) => { if (e.key === "Escape") close(); }}
        onBlur={onBlur}
        ref={fieldRef as React.RefCallback<HTMLInputElement>}
        placeholder="Type to search..."
        aria-invalid={hasError ? "true" : undefined}
        aria-describedby={hasError ? `${name}-error` : undefined}
        className={cn(
          "w-full rounded-md border px-2 py-1.5 text-sm bg-card text-foreground placeholder:text-muted-foreground",
          hasError ? "border-destructive/30 bg-destructive/5" : "border-border",
        )}
      />
      {isOpen && (
        <DropdownList
          options={filtered}
          onSelect={(val) => {
            setSearchTerm(options.find((o) => o.value === val)?.label ?? val);
            close();
            onChange(val);
          }}
          isSelected={(v) => v === value}
        />
      )}
      <ErrorMsg id={`${name}-error`} msg={errorMessage} show={hasError} />
    </div>
  );
}

function MultiTypeAhead({
  value: selected,
  onChange,
  onBlur,
  fieldRef,
  name,
  options,
  hasError,
  errorMessage,
}: MultiInnerProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [filtered, setFiltered] = useState<VocabOption[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const doFilter = useDebouncedCallback((term: string) => {
    if (!term.trim()) { setFiltered([]); setIsOpen(false); return; }
    const lower = term.toLowerCase();
    setFiltered(options.filter((o) => o.label.toLowerCase().includes(lower)));
    setIsOpen(true);
  }, 200);

  const close = () => { setIsOpen(false); setFiltered([]); };
  useOnClickOutside(containerRef as React.RefObject<HTMLElement>, close);

  return (
    <div ref={containerRef} className="relative">
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1">
          {selected.map((val) => (
            <span key={val} className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-xs">
              {options.find((o) => o.value === val)?.label ?? val}
              <button
                type="button"
                onClick={() => onChange(selected.filter((v) => v !== val))}
                className="text-muted-foreground hover:text-foreground"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <input
        type="text"
        value={searchTerm}
        onChange={(e) => { setSearchTerm(e.target.value); doFilter(e.target.value); }}
        onKeyDown={(e) => { if (e.key === "Escape") close(); }}
        onBlur={onBlur}
        ref={fieldRef as React.RefCallback<HTMLInputElement>}
        placeholder="Type to search..."
        aria-invalid={hasError ? "true" : undefined}
        aria-describedby={hasError ? `${name}-error` : undefined}
        className={cn(
          "w-full rounded-md border px-2 py-1.5 text-sm bg-card text-foreground placeholder:text-muted-foreground",
          hasError ? "border-destructive/30 bg-destructive/5" : "border-border",
        )}
      />
      {isOpen && (
        <DropdownList
          options={filtered}
          onSelect={(val) => {
            if (!selected.includes(val)) {
              onChange([...selected, val]);
            }
            setSearchTerm("");
            close();
          }}
          isSelected={(v) => selected.includes(v)}
        />
      )}
      <ErrorMsg id={`${name}-error`} msg={errorMessage} show={hasError} />
    </div>
  );
}

function DropdownList({
  options,
  onSelect,
  isSelected,
}: {
  options: VocabOption[];
  onSelect: (val: string) => void;
  isSelected: (val: string) => boolean;
}) {
  const visible = options.slice(0, MAX_VISIBLE);
  const remaining = options.length - MAX_VISIBLE;

  return (
    <ul className="absolute z-50 mt-1 w-full rounded-md border border-border bg-card shadow-lg max-h-48 overflow-y-auto">
      {visible.length === 0 && (
        <li className="px-2 py-1.5 text-sm text-muted-foreground">No matches</li>
      )}
      {visible.map((opt) => (
        <li
          key={opt.value}
          role="option"
          aria-selected={isSelected(opt.value)}
          onClick={() => onSelect(opt.value)}
          className="px-2 py-1.5 text-sm cursor-pointer hover:bg-accent hover:text-accent-foreground"
        >
          {opt.label}
        </li>
      ))}
      {remaining > 0 && (
        <li className="px-2 py-1.5 text-xs text-muted-foreground">{remaining} more...</li>
      )}
    </ul>
  );
}

function ErrorMsg({ id, msg, show }: { id: string; msg: string | undefined; show: boolean }) {
  if (!show || msg == null) return null;
  return (
    <p id={id} role="alert" className="mt-1 text-xs text-destructive">{msg}</p>
  );
}
