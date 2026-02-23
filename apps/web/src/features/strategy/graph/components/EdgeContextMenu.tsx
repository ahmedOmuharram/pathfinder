"use client";

import { useEffect, useRef } from "react";
import type { Edge } from "reactflow";
import { CombineOperator } from "@pathfinder/shared";
import type { StrategyStep } from "@/features/strategy/types";
import { inferStepKind } from "@/lib/strategyGraph";

const COMBINE_OPERATORS: readonly CombineOperator[] = [
  CombineOperator.INTERSECT,
  CombineOperator.UNION,
  CombineOperator.MINUS_LEFT,
  CombineOperator.MINUS_RIGHT,
];

interface EdgeContextMenuProps {
  edge: Edge;
  x: number;
  y: number;
  steps: StrategyStep[];
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

  // Click-outside and Escape key to close
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onClose();
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    // Use a timeout to avoid the current click from immediately closing
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handleClickOutside);
    }, 0);
    document.addEventListener("keydown", handleEscape);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [onClose]);

  const targetStep = steps.find((s) => s.id === edge.target);
  const isCombineEdge = targetStep && inferStepKind(targetStep) === "combine";

  return (
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[160px] -translate-x-1/2 -translate-y-1/2 rounded-md border border-slate-200 bg-white p-1 shadow-lg"
      style={{ left: x, top: y }}
      role="menu"
      aria-label="Edge actions"
    >
      {isCombineEdge && (
        <>
          <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Change operator
          </div>
          {COMBINE_OPERATORS.map((op) => (
            <button
              key={op}
              type="button"
              role="menuitem"
              className={`w-full rounded px-2 py-1 text-left text-xs font-medium hover:bg-slate-50 ${
                targetStep.operator === op
                  ? "text-slate-900 font-bold"
                  : "text-slate-700"
              }`}
              onClick={() => onChangeOperator(edge.target, op)}
            >
              {op}
              {targetStep.operator === op && (
                <span className="ml-1 text-slate-400">(current)</span>
              )}
            </button>
          ))}
          <div className="my-1 h-px bg-slate-100" />
        </>
      )}
      <button
        type="button"
        role="menuitem"
        className="w-full rounded px-2 py-1 text-left text-xs font-medium text-red-700 hover:bg-red-50"
        onClick={() => onDeleteEdge(edge)}
      >
        Delete edge
      </button>
    </div>
  );
}
