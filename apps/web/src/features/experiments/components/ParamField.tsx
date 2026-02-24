import { useMemo } from "react";
import type { OptimizeSpec, ParamSpec } from "@pathfinder/shared";
import { Target } from "lucide-react";
import {
  flattenVocab,
  isOptimizable,
  isParamRequired,
  isMultiPickParam,
  isParamEmpty,
} from "./paramUtils";

interface ParamFieldProps {
  spec: ParamSpec;
  value: string;
  onChange: (val: string) => void;
  optimizeSpec: OptimizeSpec | null;
  onOptimizeChange: (spec: OptimizeSpec | null) => void;
  showValidation?: boolean;
}

export function ParamField({
  spec,
  value,
  onChange,
  optimizeSpec,
  onOptimizeChange,
  showValidation = false,
}: ParamFieldProps) {
  const label = spec.displayName || spec.name;
  const isMultiPick = isMultiPickParam(spec);

  const vocabEntries = useMemo(
    () => (spec.vocabulary ? flattenVocab(spec.vocabulary) : []),
    [spec.vocabulary],
  );

  const canOptimize = isOptimizable(spec);
  const isOptimizing = optimizeSpec !== null;
  const isNumeric = spec.type === "number" || spec.type === "number-range";
  const required = isParamRequired(spec);
  const empty = isParamEmpty(spec, value);
  const hasError = showValidation && required && empty && !isOptimizing;

  const handleToggleOptimize = () => {
    if (isOptimizing) {
      onOptimizeChange(null);
    } else if (isNumeric) {
      onOptimizeChange({ name: spec.name, type: "numeric" });
    } else if (vocabEntries.length > 0) {
      onOptimizeChange({ name: spec.name, type: "categorical" });
    } else {
      onOptimizeChange({ name: spec.name, type: "numeric" });
    }
  };

  const labelRow = (
    <div className="mb-1 flex items-center gap-1.5">
      <label className="text-xs font-medium text-muted-foreground">
        {label}
        <span className="ml-1 font-normal text-muted-foreground">({spec.name})</span>
        {required && !isOptimizing && (
          <span className="ml-1 text-xs font-semibold text-red-400">*</span>
        )}
        {isMultiPick && <span className="ml-1 text-xs text-primary">multi-select</span>}
      </label>
      {canOptimize && (
        <button
          type="button"
          onClick={handleToggleOptimize}
          className={`ml-auto flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium transition ${
            isOptimizing
              ? "bg-amber-100 text-amber-700"
              : "text-muted-foreground hover:bg-muted hover:text-muted-foreground"
          }`}
        >
          <Target className="h-3 w-3" />
          {isOptimizing ? "Optimizing" : "Optimize"}
        </button>
      )}
    </div>
  );

  const errorBorder = hasError ? "border-red-300" : "border-border";
  const errorRing = hasError ? "focus:border-red-400" : "focus:border-input";

  // --- Optimize mode: numeric range ---
  if (
    isOptimizing &&
    (optimizeSpec.type === "numeric" || optimizeSpec.type === "integer")
  ) {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50/50 p-2">
        {labelRow}
        <div className="flex items-center gap-2">
          <div className="flex-1">
            <label className="mb-0.5 block text-xs text-muted-foreground">Min</label>
            <input
              type="number"
              value={optimizeSpec.min ?? ""}
              onChange={(e) =>
                onOptimizeChange({
                  ...optimizeSpec,
                  min: e.target.value ? Number(e.target.value) : undefined,
                })
              }
              placeholder="Auto"
              className="w-full rounded border border-amber-200 bg-card px-2 py-1 text-xs outline-none placeholder:text-muted-foreground focus:border-amber-300"
            />
          </div>
          <div className="flex-1">
            <label className="mb-0.5 block text-xs text-muted-foreground">Max</label>
            <input
              type="number"
              value={optimizeSpec.max ?? ""}
              onChange={(e) =>
                onOptimizeChange({
                  ...optimizeSpec,
                  max: e.target.value ? Number(e.target.value) : undefined,
                })
              }
              placeholder="Auto"
              className="w-full rounded border border-amber-200 bg-card px-2 py-1 text-xs outline-none placeholder:text-muted-foreground focus:border-amber-300"
            />
          </div>
          <div className="w-20">
            <label className="mb-0.5 block text-xs text-muted-foreground">Step</label>
            <input
              type="number"
              value={optimizeSpec.step ?? ""}
              onChange={(e) =>
                onOptimizeChange({
                  ...optimizeSpec,
                  step: e.target.value ? Number(e.target.value) : undefined,
                })
              }
              placeholder="Auto"
              className="w-full rounded border border-amber-200 bg-card px-2 py-1 text-xs outline-none placeholder:text-muted-foreground focus:border-amber-300"
            />
          </div>
        </div>
        <div className="mt-1 text-xs text-amber-600">
          Leave blank to use the full parameter range
        </div>
      </div>
    );
  }

  // --- Optimize mode: categorical choices ---
  if (isOptimizing && vocabEntries.length > 0) {
    const selectedChoices = new Set(optimizeSpec.choices ?? []);
    const toggleChoice = (v: string) => {
      const next = new Set(selectedChoices);
      if (next.has(v)) next.delete(v);
      else next.add(v);
      const choices = Array.from(next);
      onOptimizeChange({
        ...optimizeSpec,
        choices: choices.length > 0 ? choices : undefined,
      });
    };

    return (
      <div className="rounded-md border border-amber-200 bg-amber-50/50 p-2">
        {labelRow}
        <div className="mb-1 text-xs text-amber-600">
          Select values to try (leave all unchecked to try all)
        </div>
        <div className="max-h-40 overflow-y-auto rounded-md border border-amber-200 bg-card">
          {vocabEntries.map((entry) => (
            <label
              key={entry.value}
              className="flex items-center gap-2 px-2 py-1 text-xs text-foreground hover:bg-amber-50"
            >
              <input
                type="checkbox"
                checked={selectedChoices.has(entry.value)}
                onChange={() => toggleChoice(entry.value)}
                className="h-3 w-3 rounded border-input"
              />
              {entry.display}
            </label>
          ))}
        </div>
        {selectedChoices.size > 0 && (
          <div className="mt-0.5 text-xs text-amber-600">
            {selectedChoices.size} of {vocabEntries.length} selected
          </div>
        )}
      </div>
    );
  }

  // --- Normal mode (not optimizing) ---

  if (vocabEntries.length > 0) {
    if (isMultiPick) {
      const selected = new Set(value ? value.split(",") : []);
      const toggle = (v: string) => {
        const next = new Set(selected);
        if (next.has(v)) next.delete(v);
        else next.add(v);
        onChange(Array.from(next).join(","));
      };

      return (
        <div>
          {labelRow}
          <div
            className={`max-h-40 overflow-y-auto rounded-md border bg-card ${hasError ? "border-red-300" : "border-border"}`}
          >
            {vocabEntries.map((entry) => (
              <label
                key={entry.value}
                className="flex items-center gap-2 px-2 py-1 text-xs text-foreground hover:bg-muted"
              >
                <input
                  type="checkbox"
                  checked={selected.has(entry.value)}
                  onChange={() => toggle(entry.value)}
                  className="h-3 w-3 rounded border-input"
                />
                {entry.display}
              </label>
            ))}
          </div>
          {selected.size > 0 ? (
            <div className="mt-0.5 text-xs text-muted-foreground">
              {selected.size} selected
            </div>
          ) : hasError ? (
            <div className="mt-0.5 text-xs text-destructive">
              Select at least one value
            </div>
          ) : null}
        </div>
      );
    }

    return (
      <div>
        {labelRow}
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full rounded-md border px-3 py-1.5 text-sm text-foreground outline-none ${errorBorder} ${errorRing}`}
        >
          <option value="">— select —</option>
          {vocabEntries.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.display}
            </option>
          ))}
        </select>
        {hasError && <div className="mt-0.5 text-xs text-destructive">Required</div>}
      </div>
    );
  }

  if (isNumeric) {
    return (
      <div>
        {labelRow}
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Default"
          className={`w-full rounded-md border px-3 py-1.5 text-sm outline-none placeholder:text-muted-foreground ${errorBorder} ${errorRing}`}
        />
        {hasError && <div className="mt-0.5 text-xs text-destructive">Required</div>}
      </div>
    );
  }

  if (spec.type === "input-step") {
    return null;
  }

  return (
    <div>
      {labelRow}
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Default"
        className={`w-full rounded-md border px-3 py-1.5 text-sm outline-none placeholder:text-muted-foreground ${errorBorder} ${errorRing}`}
      />
      {hasError && <div className="mt-0.5 text-xs text-destructive">Required</div>}
    </div>
  );
}
