import type { ParamWidgetProps } from "./types";

export function StringParam({
  spec,
  value,
  onChangeSingle,
  fieldBorderClass,
}: ParamWidgetProps) {
  const isNumeric =
    spec.isNumber === true ||
    ["number", "integer", "float"].includes((spec.type ?? "").toLowerCase());

  return (
    <input
      type={isNumeric ? "number" : "text"}
      value={value ?? ""}
      onChange={(e) => onChangeSingle(e.target.value)}
      required={spec.allowEmptyValue === false}
      min={isNumeric && spec.min != null ? spec.min : undefined}
      max={isNumeric && spec.max != null ? spec.max : undefined}
      step={isNumeric && spec.increment != null ? spec.increment : undefined}
      className={`w-full rounded-md border px-2 py-1.5 text-sm bg-card text-foreground ${fieldBorderClass ?? "border-border"}`}
    />
  );
}
