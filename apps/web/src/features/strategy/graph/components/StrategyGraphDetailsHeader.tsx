"use client";

import { ChevronDown, ChevronUp } from "lucide-react";

interface StrategyGraphDetailsHeaderProps {
  detailsCollapsed: boolean;
  onToggleCollapsed: () => void;
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
  nameValue,
  onNameChange,
  onNameCommit,
  descriptionValue,
  onDescriptionChange,
  onDescriptionCommit,
}: StrategyGraphDetailsHeaderProps) {
  return (
    <div className="border-b border-slate-200 bg-white px-3 pb-1.5 pt-0">
      <div
        className="overflow-hidden transition-[height,opacity] duration-200"
        style={{
          height: detailsCollapsed ? 0 : "auto",
          opacity: detailsCollapsed ? 0 : 1,
        }}
      >
        <div className="mt-0.5 flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-[240px] flex-1 flex-col gap-2">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Strategy name
              </div>
              <input
                value={nameValue}
                onChange={(event) => onNameChange(event.target.value)}
                onBlur={onNameCommit}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    onNameCommit();
                  }
                }}
                className="mt-1 w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-[13px] font-semibold text-slate-800 outline-none transition focus:border-slate-300 focus:ring-1 focus:ring-slate-200"
              />
            </div>
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Description
              </div>
              <textarea
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
      >
        {detailsCollapsed ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
        <span className="text-[11px] font-semibold uppercase tracking-wide">
          {detailsCollapsed ? "Expand" : "Collapse"}
        </span>
      </button>
    </div>
  );
}

