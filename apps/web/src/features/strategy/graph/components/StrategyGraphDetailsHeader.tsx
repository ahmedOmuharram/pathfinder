"use client";

import { ChevronDown, ChevronUp } from "lucide-react";
import { useStrategyGraphCtx } from "@/features/strategy/graph/StrategyGraphContext";
import { Label } from "@/lib/components/ui/Label";

export function StrategyGraphDetailsHeader() {
  const {
    detailsCollapsed,
    toggleDetailsCollapsed,
    descriptionValue,
    setDescriptionValue,
    handleDescriptionCommit,
  } = useStrategyGraphCtx();

  return (
    <div className="border-b border-border bg-card px-3 pb-1.5 pt-0">
      {/* CSS grid row transition: grid-template-rows 0fr <-> 1fr animates smoothly */}
      <div
        className="grid transition-[grid-template-rows] duration-200 ease-in-out"
        style={{
          gridTemplateRows: detailsCollapsed ? "0fr" : "1fr",
        }}
      >
        <div className="overflow-hidden">
          <div className="mt-0.5">
            <div>
              <Label
                htmlFor="strategy-description-input"
                className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
              >
                Description
              </Label>
              <textarea
                id="strategy-description-input"
                value={descriptionValue}
                onChange={(event) => setDescriptionValue(event.target.value)}
                onBlur={() => void handleDescriptionCommit()}
                rows={2}
                placeholder="Add a short description of this strategy"
                className="mt-1 w-full resize-none rounded-md border border-border px-2.5 py-1.5 text-sm text-foreground outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={toggleDetailsCollapsed}
        className="mt-1.5 flex w-full items-center justify-center gap-2 text-muted-foreground transition-colors duration-150 hover:text-foreground"
        aria-label={detailsCollapsed ? "Expand details" : "Collapse details"}
        aria-expanded={!detailsCollapsed}
      >
        {detailsCollapsed ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronUp className="h-4 w-4" />
        )}
        <span className="text-xs font-semibold uppercase tracking-wide">
          {detailsCollapsed ? "Expand" : "Collapse"}
        </span>
      </button>
    </div>
  );
}
