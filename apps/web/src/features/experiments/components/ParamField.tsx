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
      <label className="text-[11px] font-medium text-slate-600">
        {label}
        <span className="ml-1 font-normal text-slate-400">({spec.name})</span>
        {required && !isOptimizing && (
          <span className="ml-1 text-[10px] font-semibold text-red-400">*</span>
        )}
        {isMultiPick && (
          <span className="ml-1 text-[10px] text-indigo-500">multi-select</span>
        )}
      </label>
      {canOptimize && (
        <button
          type="button"
          onClick={handleToggleOptimize}
          className={`ml-auto flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium transition ${
            isOptimizing
              ? "bg-amber-100 text-amber-700"
              : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          }`}
        >
          <Target className="h-3 w-3" />
          {isOptimizing ? "Optimizing" : "Optimize"}
        </button>
      )}
    </div>
  );

  const errorBorder = hasError ? "border-red-300" : "border-slate-200";
  const errorRing = hasError ? "focus:border-red-400" : "focus:border-slate-300";

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
            <label className="mb-0.5 block text-[10px] text-slate-500">Min</label>
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
              className="w-full rounded border border-amber-200 bg-white px-2 py-1 text-[11px] outline-none placeholder:text-slate-400 focus:border-amber-300"
            />
          </div>
          <div className="flex-1">
            <label className="mb-0.5 block text-[10px] text-slate-500">Max</label>
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
              className="w-full rounded border border-amber-200 bg-white px-2 py-1 text-[11px] outline-none placeholder:text-slate-400 focus:border-amber-300"
            />
          </div>
          <div className="w-20">
            <label className="mb-0.5 block text-[10px] text-slate-500">Step</label>
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
              className="w-full rounded border border-amber-200 bg-white px-2 py-1 text-[11px] outline-none placeholder:text-slate-400 focus:border-amber-300"
            />
          </div>
        </div>
        <div className="mt-1 text-[10px] text-amber-600">
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
        <div className="mb-1 text-[10px] text-amber-600">
          Select values to try (leave all unchecked to try all)
        </div>
        <div className="max-h-40 overflow-y-auto rounded-md border border-amber-200 bg-white">
          {vocabEntries.map((entry) => (
            <label
              key={entry.value}
              className="flex items-center gap-2 px-2 py-1 text-[11px] text-slate-700 hover:bg-amber-50"
            >
              <input
                type="checkbox"
                checked={selectedChoices.has(entry.value)}
                onChange={() => toggleChoice(entry.value)}
                className="h-3 w-3 rounded border-slate-300"
              />
              {entry.display}
            </label>
          ))}
        </div>
        {selectedChoices.size > 0 && (
          <div className="mt-0.5 text-[10px] text-amber-600">
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
            className={`max-h-40 overflow-y-auto rounded-md border bg-white ${hasError ? "border-red-300" : "border-slate-200"}`}
          >
            {vocabEntries.map((entry) => (
              <label
                key={entry.value}
                className="flex items-center gap-2 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50"
              >
                <input
                  type="checkbox"
                  checked={selected.has(entry.value)}
                  onChange={() => toggle(entry.value)}
                  className="h-3 w-3 rounded border-slate-300"
                />
                {entry.display}
              </label>
            ))}
          </div>
          {selected.size > 0 ? (
            <div className="mt-0.5 text-[10px] text-slate-400">
              {selected.size} selected
            </div>
          ) : hasError ? (
            <div className="mt-0.5 text-[10px] text-red-500">
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
          className={`w-full rounded-md border px-3 py-1.5 text-[12px] text-slate-700 outline-none ${errorBorder} ${errorRing}`}
        >
          <option value="">— select —</option>
          {vocabEntries.map((entry) => (
            <option key={entry.value} value={entry.value}>
              {entry.display}
            </option>
          ))}
        </select>
        {hasError && <div className="mt-0.5 text-[10px] text-red-500">Required</div>}
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
          className={`w-full rounded-md border px-3 py-1.5 text-[12px] outline-none placeholder:text-slate-400 ${errorBorder} ${errorRing}`}
        />
        {hasError && <div className="mt-0.5 text-[10px] text-red-500">Required</div>}
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
        className={`w-full rounded-md border px-3 py-1.5 text-[12px] outline-none placeholder:text-slate-400 ${errorBorder} ${errorRing}`}
      />
      {hasError && <div className="mt-0.5 text-[10px] text-red-500">Required</div>}
    </div>
  );
}
