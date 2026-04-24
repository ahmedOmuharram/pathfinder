"use client";

import { ArrowLeftRight } from "lucide-react";
import { useRef } from "react";
import { useDebounceCallback } from "usehooks-ts";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useVennState } from "../hooks/useVennState";
import { VennSvg, type VennRegion } from "./VennSvg";

const ON_CHANGE_DEBOUNCE_MS = 600;
const DEBOUNCE_MS = 1000;

const PRETTY: Record<string, string> = {
  INTERSECT: "Intersect",
  UNION: "Union",
  MINUS: "A only",
  RMINUS: "B only",
  LONLY: "Just A",
  RONLY: "Just B",
  COLOCATE: "Colocate",
};

const CYCLE: Record<VennRegion, [string, string]> = {
  A: ["LONLY", "MINUS"],
  LENS: ["INTERSECT", "UNION"],
  B: ["RONLY", "RMINUS"],
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
  const lastClickRef = useRef<{ region: VennRegion; ts: number; index: 0 | 1 } | null>(null);

  const debouncedOnChange = useDebounceCallback(onChange, ON_CHANGE_DEBOUNCE_MS);

  const click = (next: string) => {
    venn.setOperator(next);
    debouncedOnChange(next);
  };

  const swap = () => {
    const beforeOp = venn.operator;
    venn.swap();
    let nextOp: string;
    if (beforeOp === "MINUS") nextOp = "RMINUS";
    else if (beforeOp === "RMINUS") nextOp = "MINUS";
    else if (beforeOp === "LONLY") nextOp = "RONLY";
    else if (beforeOp === "RONLY") nextOp = "LONLY";
    else nextOp = beforeOp;
    debouncedOnChange.cancel();
    onChange(nextOp);
  };

  const handleRegionClick = (region: VennRegion) => {
    const now = Date.now();
    const last = lastClickRef.current;
    const isRapidRepeat =
      last !== null && last.region === region && now - last.ts < DEBOUNCE_MS;
    const nextIndex: 0 | 1 = isRapidRepeat ? (last.index === 0 ? 1 : 0) : 0;
    lastClickRef.current = { region, ts: now, index: nextIndex };
    click(CYCLE[region][nextIndex]);
  };

  const showA = venn.swappedLabels ? bLabel : aLabel;
  const showB = venn.swappedLabels ? aLabel : bLabel;

  // Background-circle fills: render the full A and/or B circle when the
  // operator selects the entire side. UNION fills both. LONLY fills A
  // (lens stays inside that fill, matching the "include all of A" semantic).
  // Region overlays are then transparent for these operators so their
  // primary/0.55 fill doesn't stack on top of the circle fill.
  const fillA = venn.operator === "UNION" || venn.operator === "LONLY";
  const fillB = venn.operator === "UNION" || venn.operator === "RONLY";

  const isRegionSelected = (region: VennRegion): boolean => {
    if (region === "A") return venn.operator === "MINUS";
    if (region === "B") return venn.operator === "RMINUS";
    return venn.operator === "INTERSECT";
  };

  return (
    <div className="flex flex-col gap-3" data-testid="venn-picker">
      <div className="flex justify-center">
        <VennSvg
          fillA={fillA}
          fillB={fillB}
          isRegionSelected={isRegionSelected}
          handleRegionClick={handleRegionClick}
          showA={showA}
          showB={showB}
          isColocate={venn.operator === "COLOCATE"}
        />
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
          value={venn.operator === "COLOCATE" ? "COLOCATE" : ""}
          onValueChange={(v) => {
            if (v === "COLOCATE" && venn.operator !== "COLOCATE") click("COLOCATE");
          }}
          variant="outline"
          size="sm"
        >
          <ToggleGroupItem value="COLOCATE" aria-label="Colocate">Colocate…</ToggleGroupItem>
        </ToggleGroup>
      </div>
    </div>
  );
}

