import type { ParamWidgetProps } from "./types";

export function SelectParam({
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
      <select
        value={value ?? ""}
        onChange={(e) => onChangeSingle(e.target.value)}
        className={`w-full rounded-md border px-2 py-1.5 text-sm bg-card text-foreground ${fieldBorderClass || "border-border"}`}
      >
        {spec.allowEmptyValue !== false && <option value="">-- Select --</option>}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    );
  }

  const allSelected = options.length > 0 && multiValue.length === options.length;

  const toggleAll = () => {
    onChangeMulti(allSelected ? [] : options.map((o) => o.value));
  };

  const toggle = (val: string) => {
    onChangeMulti(
      multiValue.includes(val)
        ? multiValue.filter((v) => v !== val)
        : [...multiValue, val],
    );
  };

  return (
    <div
      className={`rounded-md border ${fieldBorderClass || "border-border"} bg-card max-h-48 overflow-y-auto p-2`}
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
