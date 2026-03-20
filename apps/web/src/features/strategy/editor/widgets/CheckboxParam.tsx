import type { ParamWidgetProps } from "./types";

export function CheckboxParam({
  spec,
  value,
  multi,
  multiValue,
  options,
  onChangeSingle,
  onChangeMulti,
  fieldBorderClass,
}: ParamWidgetProps) {
  if (!multi) {
    return (
      <div
        className={`rounded-md border ${fieldBorderClass ?? "border-border"} bg-card p-2 space-y-1`}
      >
        {options.map((opt) => (
          <label key={opt.value} className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name={spec.name}
              value={opt.value}
              checked={value === opt.value}
              onChange={() => onChangeSingle(opt.value)}
              className="accent-primary"
            />
            {opt.label}
          </label>
        ))}
      </div>
    );
  }

  const allSelected = options.length > 0 && multiValue.length === options.length;

  const toggleAll = () => onChangeMulti(allSelected ? [] : options.map((o) => o.value));

  const toggle = (val: string) => {
    onChangeMulti(
      multiValue.includes(val)
        ? multiValue.filter((v) => v !== val)
        : [...multiValue, val],
    );
  };

  return (
    <div
      className={`rounded-md border ${fieldBorderClass ?? "border-border"} bg-card max-h-48 overflow-y-auto p-2`}
    >
      {options.length > 3 && (
        <label className="flex items-center gap-2 text-xs text-muted-foreground mb-1 pb-1 border-b border-border">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={toggleAll}
            className="accent-primary"
          />
          Select all ({options.length})
        </label>
      )}
      {options.map((opt) => (
        <label key={opt.value} className="flex items-center gap-2 text-sm py-0.5">
          <input
            type="checkbox"
            checked={multiValue.includes(opt.value)}
            onChange={() => toggle(opt.value)}
            className="accent-primary"
          />
          {opt.label}
        </label>
      ))}
    </div>
  );
}
