"use client";

import { useState } from "react";

import type {
  VolcanoDirection,
  VolcanoThresholds,
} from "@/lib/components/charts/types";

const INPUT_CLASS =
  "h-8 w-28 rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring";

const DIRECTIONS: { value: VolcanoDirection; label: string }[] = [
  { value: "upAndDown", label: "Up and down" },
  { value: "upOnly", label: "Up only" },
  { value: "downOnly", label: "Down only" },
];

export interface VolcanoControlsProps {
  thresholds: VolcanoThresholds;
  /** A new payload re-seeds the typed values from the adopted thresholds. */
  resetToken: unknown;
  onChange: (next: VolcanoThresholds) => void;
}

function typedValues(thresholds: VolcanoThresholds) {
  return {
    effect: String(thresholds.effectSizeThreshold),
    significance: String(thresholds.significanceThreshold),
  };
}

function toDirection(value: string): VolcanoDirection {
  if (value === "upOnly") return "upOnly";
  return value === "downOnly" ? "downOnly" : "upAndDown";
}

export function VolcanoControls({
  thresholds,
  resetToken,
  onChange,
}: VolcanoControlsProps) {
  const [typed, setTyped] = useState(() => typedValues(thresholds));
  const [seen, setSeen] = useState(resetToken);
  if (seen !== resetToken) {
    setSeen(resetToken);
    setTyped(typedValues(thresholds));
  }

  const edit = (field: "effect" | "significance", raw: string) => {
    setTyped({ ...typed, [field]: raw });
    const parsed = Number.parseFloat(raw);
    if (!Number.isFinite(parsed)) return;
    onChange(
      field === "effect"
        ? { ...thresholds, effectSizeThreshold: parsed }
        : { ...thresholds, significanceThreshold: parsed },
    );
  };

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="space-y-1">
        <label
          htmlFor="eda-volcano-effect"
          className="block text-[11px] text-muted-foreground"
        >
          Effect size threshold
        </label>
        <input
          id="eda-volcano-effect"
          type="number"
          step="0.1"
          className={INPUT_CLASS}
          value={typed.effect}
          onChange={(event) => edit("effect", event.target.value)}
        />
      </div>
      <div className="space-y-1">
        <label
          htmlFor="eda-volcano-significance"
          className="block text-[11px] text-muted-foreground"
        >
          Significance threshold
        </label>
        <input
          id="eda-volcano-significance"
          type="number"
          step="0.001"
          className={INPUT_CLASS}
          value={typed.significance}
          onChange={(event) => edit("significance", event.target.value)}
        />
      </div>
      <div className="space-y-1">
        <label
          htmlFor="eda-volcano-direction"
          className="block text-[11px] text-muted-foreground"
        >
          Direction
        </label>
        <select
          id="eda-volcano-direction"
          className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          value={thresholds.direction}
          onChange={(event) =>
            onChange({ ...thresholds, direction: toDirection(event.target.value) })
          }
        >
          {DIRECTIONS.map((direction) => (
            <option key={direction.value} value={direction.value}>
              {direction.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
