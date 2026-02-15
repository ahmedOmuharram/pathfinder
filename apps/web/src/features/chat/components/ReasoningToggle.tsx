/**
 * ReasoningToggle — compact three-segment toggle for reasoning effort.
 *
 * Only visible when the selected model supports reasoning.
 */

"use client";

import type { ReasoningEffort } from "@pathfinder/shared";

const OPTIONS: { value: ReasoningEffort; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Med" },
  { value: "high", label: "High" },
];

interface ReasoningToggleProps {
  value: ReasoningEffort;
  onChange: (effort: ReasoningEffort) => void;
  disabled?: boolean;
}

export function ReasoningToggle({ value, onChange, disabled }: ReasoningToggleProps) {
  return (
    <div
      className="inline-flex items-center rounded-md border border-slate-200 bg-white text-[11px]"
      role="radiogroup"
      aria-label="Reasoning effort"
    >
      {OPTIONS.map((opt) => {
        const isActive = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={isActive}
            disabled={disabled}
            onClick={() => onChange(opt.value)}
            className={`px-2 py-1 font-medium transition-colors first:rounded-l-[5px] last:rounded-r-[5px] ${
              isActive
                ? "bg-slate-900 text-white"
                : "text-slate-500 hover:bg-slate-50 hover:text-slate-700"
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
