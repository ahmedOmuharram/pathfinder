"use client";

import { ArrowLeftRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cn } from "@/lib/utils/cn";
import { useVennState } from "../hooks/useVennState";

const REGION_PATHS = {
  MINUS: "M 110 28 A 62 62 0 1 0 110 152 A 62 62 0 0 1 110 28 Z",
  INTERSECT: "M 110 28 A 62 62 0 0 1 110 152 A 62 62 0 0 1 110 28 Z",
  RMINUS: "M 170 28 A 62 62 0 1 1 170 152 A 62 62 0 0 0 170 28 Z",
} as const;

const PRETTY: Record<string, string> = {
  INTERSECT: "Intersect",
  UNION: "Union",
  MINUS: "A only",
  RMINUS: "B only",
  COLOCATE: "Colocate",
};

interface VennPickerProps {
  operator: string;
  onChange: (next: string) => void;
  aLabel?: string;
  bLabel?: string;
}

export function VennPicker({
  operator,
  onChange,
  aLabel = "A",
  bLabel = "B",
}: VennPickerProps) {
  const venn = useVennState(operator);

  const swap = () => {
    const beforeOp = venn.operator;
    venn.swap();
    if (beforeOp === "MINUS") {
      onChange("RMINUS");
    } else if (beforeOp === "RMINUS") {
      onChange("MINUS");
    } else {
      onChange(beforeOp);
    }
  };

  const isSelected = (region: keyof typeof REGION_PATHS) =>
    venn.operator === region || venn.operator === "UNION";

  const showA = venn.swappedLabels ? bLabel : aLabel;
  const showB = venn.swappedLabels ? aLabel : bLabel;

  const click = (next: string) => {
    venn.setOperator(next);
    onChange(next);
  };

  const isUnionVisuallyFilled = venn.operator === "UNION";

  return (
    <div className="flex flex-col gap-3" data-testid="venn-picker">
      <div className="flex justify-center">
        <svg
          viewBox="0 0 280 180"
          width="280"
          height="180"
          role="img"
          aria-label="Venn region picker"
          className="select-none"
        >
          {/* Filled circles when UNION (visual only — picks happen via region clicks or presets) */}
          {isUnionVisuallyFilled && (
            <>
              <circle cx="110" cy="90" r="62" fill="hsl(var(--primary) / 0.55)" />
              <circle cx="170" cy="90" r="62" fill="hsl(var(--primary) / 0.55)" />
            </>
          )}

          {/* Outline circles */}
          <circle cx="110" cy="90" r="62" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground" />
          <circle cx="170" cy="90" r="62" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground" />

          {/* Clickable regions */}
          <RegionPath
            label="A only"
            d={REGION_PATHS.MINUS}
            selected={isSelected("MINUS")}
            onClick={() => click("MINUS")}
          />
          <RegionPath
            label="Intersection region"
            d={REGION_PATHS.INTERSECT}
            selected={isSelected("INTERSECT")}
            onClick={() => click("INTERSECT")}
          />
          <RegionPath
            label="B only"
            d={REGION_PATHS.RMINUS}
            selected={isSelected("RMINUS")}
            onClick={() => click("RMINUS")}
          />

          {/* Step labels */}
          <text x="60" y="170" textAnchor="middle" className="fill-muted-foreground text-xs">
            {showA}
          </text>
          <text x="220" y="170" textAnchor="middle" className="fill-muted-foreground text-xs">
            {showB}
          </text>
        </svg>
      </div>

      <div className="flex items-center justify-between gap-2">
        <p className="text-sm text-foreground" data-slot="venn-readout">
          Operator:{" "}
          <span className="font-semibold">{venn.operator}</span>{" "}
          <span className="text-muted-foreground">({PRETTY[venn.operator] ?? venn.operator})</span>
        </p>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={swap}
          className="gap-1.5"
        >
          <ArrowLeftRight className="size-3.5" />
          Swap A↔B
        </Button>
      </div>

      <div className="flex items-center justify-center">
        <ToggleGroup
          type="single"
          value={venn.operator}
          onValueChange={(v) => {
            if (v !== "" && v !== venn.operator) click(v);
          }}
          variant="outline"
          size="sm"
        >
          <ToggleGroupItem value="UNION" aria-label="Union">Union</ToggleGroupItem>
          <ToggleGroupItem value="INTERSECT" aria-label="Intersect">∩ Both</ToggleGroupItem>
          <ToggleGroupItem value="COLOCATE" aria-label="Colocate">Colocate…</ToggleGroupItem>
        </ToggleGroup>
      </div>
    </div>
  );
}

function RegionPath({
  label,
  d,
  selected,
  onClick,
}: {
  label: string;
  d: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <path
      d={d}
      role="button"
      aria-label={label}
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className={cn(
        "cursor-pointer outline-none transition-[fill] duration-150 ease-[cubic-bezier(.4,0,.2,1)] focus-visible:stroke-ring focus-visible:stroke-2",
        selected
          ? "fill-[hsl(var(--primary)/0.55)] hover:fill-[hsl(var(--primary)/0.7)]"
          : "fill-transparent hover:fill-[hsl(var(--primary)/0.18)]",
      )}
    />
  );
}
