import { useState, useCallback, useRef, useEffect } from "react";
import { useDebouncedCallback } from "use-debounce";
import type { ParamWidgetProps } from "./types";

const MAX_VISIBLE = 50;

export function TypeAheadParam({
  spec,
  value,
  multi,
  multiValue,
  options,
  onChangeSingle,
  onChangeMulti,
  fieldBorderClass,
}: ParamWidgetProps) {
  const currentLabel =
    !multi && value ? (options.find((o) => o.value === value)?.label ?? value) : "";

  const [searchTerm, setSearchTerm] = useState(currentLabel);
  const [filteredOptions, setFilteredOptions] = useState<typeof options>([]);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Sync searchTerm with external value changes (single-pick only).
  // Uses the React-recommended "set state during render" pattern for derived state.
  const [prevValue, setPrevValue] = useState(value);
  if (!multi && value !== prevValue) {
    setPrevValue(value);
    const label = value ? (options.find((o) => o.value === value)?.label ?? value) : "";
    if (label !== searchTerm) {
      setSearchTerm(label);
    }
  }

  const filterOptions = useDebouncedCallback((term: string) => {
    if (!term.trim()) {
      setFilteredOptions([]);
      setIsOpen(false);
      return;
    }
    const lower = term.toLowerCase();
    const matches = options.filter((opt) => opt.label.toLowerCase().includes(lower));
    setFilteredOptions(matches);
    setIsOpen(true);
  }, 200);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const term = e.target.value;
      setSearchTerm(term);
      filterOptions(term);
    },
    [filterOptions],
  );

  const handleSelectSingle = useCallback(
    (val: string) => {
      const opt = options.find((o) => o.value === val);
      setSearchTerm(opt?.label ?? val);
      setIsOpen(false);
      setFilteredOptions([]);
      onChangeSingle(val);
    },
    [onChangeSingle, options],
  );

  const handleSelectMulti = useCallback(
    (val: string) => {
      if (!multiValue.includes(val)) {
        onChangeMulti([...multiValue, val]);
      }
      setSearchTerm("");
      setIsOpen(false);
      setFilteredOptions([]);
    },
    [multiValue, onChangeMulti],
  );

  const handleRemoveChip = useCallback(
    (val: string) => {
      onChangeMulti(multiValue.filter((v) => v !== val));
    },
    [multiValue, onChangeMulti],
  );

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setIsOpen(false);
      setFilteredOptions([]);
    }
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const visibleOptions = filteredOptions.slice(0, MAX_VISIBLE);
  const remaining = filteredOptions.length - MAX_VISIBLE;

  return (
    <div ref={containerRef} className="relative">
      {multi && multiValue.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1">
          {multiValue.map((val) => {
            const opt = options.find((o) => o.value === val);
            return (
              <span
                key={val}
                className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-xs"
              >
                {opt?.label ?? val}
                <button
                  type="button"
                  onClick={() => handleRemoveChip(val)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  ×
                </button>
              </span>
            );
          })}
        </div>
      )}
      <input
        type="text"
        value={searchTerm}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        placeholder="Type to search..."
        className={`w-full rounded-md border px-2 py-1.5 text-sm bg-card text-foreground placeholder:text-muted-foreground ${fieldBorderClass || "border-border"}`}
      />
      {isOpen && (
        <ul className="absolute z-50 mt-1 w-full rounded-md border border-border bg-card shadow-lg max-h-48 overflow-y-auto">
          {visibleOptions.length === 0 && (
            <li className="px-2 py-1.5 text-sm text-muted-foreground">No matches</li>
          )}
          {visibleOptions.map((opt) => (
            <li
              key={opt.value}
              role="option"
              aria-selected={
                multi ? multiValue.includes(opt.value) : value === opt.value
              }
              onClick={() =>
                multi ? handleSelectMulti(opt.value) : handleSelectSingle(opt.value)
              }
              className="px-2 py-1.5 text-sm cursor-pointer hover:bg-accent hover:text-accent-foreground"
            >
              {opt.label}
            </li>
          ))}
          {remaining > 0 && (
            <li className="px-2 py-1.5 text-xs text-muted-foreground">
              {remaining} more...
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
