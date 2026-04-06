"use client";

import { useState } from "react";

import type { PlannedParameter, ParamStatus } from "@/lib/types/plan";

interface PlanParameterFieldProps {
  param: PlannedParameter;
  onChange: (name: string, value: unknown) => void;
  disabled: boolean;
}

const statusBadge: Record<ParamStatus, { label: string; className: string }> = {
  set: { label: "Set", className: "bg-emerald-500/20 text-emerald-400" },
  default: { label: "Default", className: "bg-zinc-500/20 text-zinc-400" },
  needs_discovery: { label: "Needs Discovery", className: "bg-orange-500/20 text-orange-400" },
  needs_user_input: { label: "Needs Input", className: "bg-yellow-500/20 text-yellow-400" },
  user_set: { label: "User Set", className: "bg-blue-500/20 text-blue-400" },
};

function MultiPickButtons({
  options,
  selected,
  onToggle,
  disabled,
}: {
  options: string[];
  selected: Set<string>;
  onToggle: (option: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          disabled={disabled}
          onClick={() => onToggle(opt)}
          className={`rounded-md border px-2 py-0.5 text-xs transition-colors ${
            selected.has(opt)
              ? "border-purple-500/50 bg-purple-500/20 text-purple-300"
              : "border-border bg-muted text-muted-foreground hover:bg-accent"
          } ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}

export function PlanParameterField({ param, onChange, disabled }: PlanParameterFieldProps) {
  const badge = statusBadge[param.status];

  const initialMultiPick = (): Set<string> => {
    if (Array.isArray(param.value)) return new Set(param.value.map(String));
    if (typeof param.value === "string" && param.value.includes(",")) {
      return new Set(param.value.split(",").map((s) => s.trim()).filter(Boolean));
    }
    return new Set();
  };

  const [multiSelected, setMultiSelected] = useState<Set<string>>(initialMultiPick);

  const isMultiPick = param.paramType === "multi-pick-vocabulary" && param.options !== null && param.options.length > 0;
  const isSinglePick = param.paramType === "single-pick-vocabulary" && param.options !== null && param.options.length > 0;
  const isNumberRange = param.paramType === "number-range";
  const isNumber = param.paramType === "number";

  function handleMultiToggle(option: string) {
    const next = new Set(multiSelected);
    if (next.has(option)) {
      next.delete(option);
    } else {
      next.add(option);
    }
    setMultiSelected(next);
    onChange(param.name, Array.from(next));
  }

  return (
    <div className="space-y-1">
      {/* Label row */}
      <div className="flex items-center gap-2">
        <label className="text-xs font-medium text-foreground">{param.displayName}</label>
        {param.required && (
          <span className="text-[10px] font-semibold uppercase tracking-wide text-red-400">
            required
          </span>
        )}
        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${badge.className}`}>
          {badge.label}
        </span>
      </div>

      {/* Input */}
      {isSinglePick ? (
        <select
          value={param.value != null ? String(param.value) : ""}
          disabled={disabled}
          onChange={(e) => onChange(param.name, e.target.value)}
          className="w-full rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="">Select...</option>
          {param.options!.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      ) : isMultiPick ? (
        <MultiPickButtons
          options={param.options!}
          selected={multiSelected}
          onToggle={handleMultiToggle}
          disabled={disabled}
        />
      ) : isNumberRange ? (
        <div className="flex items-center gap-2">
          <div className="flex-1">
            <span className="text-[10px] text-muted-foreground">Min</span>
            <input
              type="number"
              disabled={disabled}
              value={
                Array.isArray(param.value) && param.value.length > 0
                  ? String(param.value[0] ?? "")
                  : ""
              }
              onChange={(e) => {
                const current = Array.isArray(param.value) ? param.value : ["", ""];
                onChange(param.name, [e.target.value, current[1] ?? ""]);
              }}
              className="w-full rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>
          <div className="flex-1">
            <span className="text-[10px] text-muted-foreground">Max</span>
            <input
              type="number"
              disabled={disabled}
              value={
                Array.isArray(param.value) && param.value.length > 1
                  ? String(param.value[1] ?? "")
                  : ""
              }
              onChange={(e) => {
                const current = Array.isArray(param.value) ? param.value : ["", ""];
                onChange(param.name, [current[0] ?? "", e.target.value]);
              }}
              className="w-full rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>
        </div>
      ) : isNumber ? (
        <input
          type="number"
          disabled={disabled}
          value={param.value != null ? String(param.value) : ""}
          onChange={(e) => onChange(param.name, e.target.value)}
          className="w-full rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground disabled:cursor-not-allowed disabled:opacity-50"
        />
      ) : (
        <input
          type="text"
          disabled={disabled}
          value={param.value != null ? String(param.value) : ""}
          onChange={(e) => onChange(param.name, e.target.value)}
          className="w-full rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground disabled:cursor-not-allowed disabled:opacity-50"
        />
      )}

      {/* Description help text */}
      {param.description !== null && param.description !== "" && (
        <p className="text-[11px] leading-snug text-muted-foreground">{param.description}</p>
      )}

      {/* Rationale */}
      {param.rationale !== null && param.rationale !== "" && (
        <p className="text-[11px] italic leading-snug text-muted-foreground/70">{param.rationale}</p>
      )}
    </div>
  );
}
