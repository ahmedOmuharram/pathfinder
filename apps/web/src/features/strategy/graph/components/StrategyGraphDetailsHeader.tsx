"use client";

import { ChevronDown, ChevronUp } from "lucide-react";

interface StrategyGraphDetailsHeaderProps {
  detailsCollapsed: boolean;
  onToggleCollapsed: () => void;
  /** Strategy name is now edited via the conversation header — kept here as read-only context. */
  nameValue: string;
  onNameChange: (next: string) => void;
  onNameCommit: () => void;
  descriptionValue: string;
  onDescriptionChange: (next: string) => void;
  onDescriptionCommit: () => void;
}

export function StrategyGraphDetailsHeader({
  detailsCollapsed,
  onToggleCollapsed,
  descriptionValue,
  onDescriptionChange,
  onDescriptionCommit,
}: StrategyGraphDetailsHeaderProps) {
  return (
    <div className="border-b border-slate-200 bg-white px-3 pb-1.5 pt-0">
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
              <label
                htmlFor="strategy-description-input"
                className="text-[11px] font-semibold uppercase tracking-wide text-slate-400"
              >
                Description
              </label>
              <textarea
                id="strategy-description-input"
                value={descriptionValue}
                onChange={(event) => onDescriptionChange(event.target.value)}
                onBlur={onDescriptionCommit}
                rows={2}
                placeholder="Add a short description of this strategy"
                className="mt-1 w-full resize-none rounded-md border border-slate-200 px-2.5 py-1.5 text-[13px] text-slate-700 outline-none transition focus:border-slate-300 focus:ring-1 focus:ring-slate-200"
              />
            </div>
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={onToggleCollapsed}
        className="mt-1.5 flex w-full items-center justify-center gap-2 text-slate-400 transition hover:text-slate-600"
        aria-label={detailsCollapsed ? "Expand details" : "Collapse details"}
        aria-expanded={!detailsCollapsed}
      >
        {detailsCollapsed ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronUp className="h-4 w-4" />
        )}
        <span className="text-[11px] font-semibold uppercase tracking-wide">
          {detailsCollapsed ? "Expand" : "Collapse"}
        </span>
      </button>
    </div>
  );
}
