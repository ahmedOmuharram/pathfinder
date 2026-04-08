"use client";

import { useRef } from "react";
import { useEventListener, useOnClickOutside } from "usehooks-ts";
import type { Edge } from "@xyflow/react";
import { CombineOperator, type Step } from "@pathfinder/shared";
import { inferStepKind } from "@/lib/strategyGraph";

/** Boolean combine operators only (excludes COLOCATE). */
const COMBINE_OPERATORS: readonly CombineOperator[] = (
  Object.values(CombineOperator) as CombineOperator[]
).filter((op) => op !== CombineOperator.COLOCATE);

interface EdgeContextMenuProps {
  edge: Edge;
  x: number;
  y: number;
  steps: Step[];
  onDeleteEdge: (edge: Edge) => void;
  onChangeOperator: (stepId: string, operator: CombineOperator) => void;
  onClose: () => void;
}

/**
 * Floating context menu for edge interactions.
 * Supports "Delete edge" and "Change operator" for combine edges.
 * Includes click-outside handling.
 */
export function EdgeContextMenu({
  edge,
  x,
  y,
  steps,
  onDeleteEdge,
  onChangeOperator,
  onClose,
}: EdgeContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useOnClickOutside(menuRef as React.RefObject<HTMLElement>, onClose);

  useEventListener("keydown", (e) => {
    if (e.key === "Escape") onClose();
  });

  const targetStep = steps.find((s) => s.id === edge.target);
  const isCombineEdge = targetStep != null && inferStepKind(targetStep) === "combine";

  return (
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[160px] -translate-x-1/2 -translate-y-1/2 rounded-md border border-border bg-card p-1 shadow-lg"
      style={{ left: x, top: y }}
      role="menu"
      aria-label="Edge actions"
    >
      {isCombineEdge && (
        <>
          <div className="px-2 py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Change operator
          </div>
          {COMBINE_OPERATORS.map((op) => (
            <button
              key={op}
              type="button"
              role="menuitem"
              className={`w-full rounded px-2 py-1 text-left text-xs font-medium transition-colors duration-150 hover:bg-accent ${
                targetStep.operator === op
                  ? "text-foreground font-bold"
                  : "text-foreground"
              }`}
              onClick={() => onChangeOperator(edge.target, op)}
            >
              {op}
              {targetStep.operator === op && (
                <span className="ml-1 text-muted-foreground">(current)</span>
              )}
            </button>
          ))}
          <div className="my-1 h-px bg-border" />
        </>
      )}
      <button
        type="button"
        role="menuitem"
        className="w-full rounded px-2 py-1 text-left text-xs font-medium text-destructive transition-colors duration-150 hover:bg-destructive/5"
        onClick={() => onDeleteEdge(edge)}
      >
        Delete edge
      </button>
    </div>
  );
}
