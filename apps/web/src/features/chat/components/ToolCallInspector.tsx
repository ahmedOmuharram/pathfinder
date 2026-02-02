"use client";

import { useState } from "react";
import JSON5 from "json5";
import type { ToolCall } from "@pathfinder/shared";

interface ToolCallInspectorProps {
  toolCalls: ToolCall[];
  isActive?: boolean;
}

const TOOL_DESCRIPTIONS: Record<string, string> = {
  list_sites: "Finding available databases...",
  get_record_types: "Getting record types...",
  list_searches: "Listing available searches...",
  search_for_searches: "Searching for relevant searches...",
  get_search_parameters: "Getting search parameters...",
  create_search_step: "Creating search step...",
  combine_steps: "Combining steps...",
  transform_step: "Applying transform...",
  build_strategy: "Pushing strategy...",
  save_strategy: "Saving strategy...",
};

export function ToolCallInspector({ toolCalls, isActive = false }: ToolCallInspectorProps) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (toolCalls.length === 0) return null;

  const formatToolResult = (result: ToolCall["result"]) => {
    if (result === null || result === undefined) return null;
    if (typeof result !== "string") {
      return JSON.stringify(result, null, 2);
    }
    const normalized = result
      .replace(/\bNone\b/g, "null")
      .replace(/\bTrue\b/g, "true")
      .replace(/\bFalse\b/g, "false");
    try {
      return JSON.stringify(JSON5.parse(normalized), null, 2);
    } catch {
      return result;
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {isActive && (
          <span className="h-2 w-2 animate-pulse rounded-full bg-slate-400" />
        )}
        Tool Calls ({toolCalls.length})
      </div>
      {toolCalls.map((tc) => {
        const hasResult = tc.result !== undefined;
        const isRunning = isActive && !hasResult;
        
        return (
          <div
            key={tc.id}
            className={`overflow-hidden rounded-lg border ${
              isRunning ? "border-slate-300" : "border-slate-200"
            } bg-white`}
          >
            <button
              onClick={() => setExpanded(expanded === tc.id ? null : tc.id)}
              className="flex w-full items-center px-3 py-2 text-left text-slate-700 transition-colors hover:bg-slate-50"
            >
              <div className="flex items-center gap-2">
                {isRunning ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-400 border-t-transparent" />
                ) : (
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    Tool
                  </span>
                )}
                <div className="flex flex-col">
                  <span className="text-xs font-mono text-slate-700">{tc.name}</span>
                  {isRunning && (
                    <span className="text-[11px] text-slate-500">
                      {TOOL_DESCRIPTIONS[tc.name] || "Working..."}
                    </span>
                  )}
                </div>
              </div>
              <div className="ml-auto flex items-center gap-2">
                {hasResult && (
                  <span className="text-[11px] text-emerald-600">Done</span>
                )}
                {!isRunning && (
                  <svg
                    className={`h-4 w-4 text-slate-400 transition-transform ${
                      expanded === tc.id ? "rotate-180" : ""
                    }`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                )}
              </div>
            </button>

            {expanded === tc.id && (
              <div className="space-y-2 border-t border-slate-200 px-3 py-2">
                {Object.keys(tc.arguments || {}).length > 0 && (
                  <div>
                    <div className="mb-1 text-[11px] text-slate-500">Arguments:</div>
                    <pre className="rounded bg-slate-50 p-2 text-[11px] text-slate-700 overflow-x-auto whitespace-pre-wrap break-words">
                      {JSON.stringify(tc.arguments, null, 2)}
                    </pre>
                  </div>
                )}
                {tc.result && (
                  <div>
                    <div className="mb-1 text-[11px] text-slate-500">Result:</div>
                    <pre className="max-h-40 rounded bg-slate-50 p-2 text-[11px] text-slate-700 overflow-x-auto whitespace-pre-wrap break-words">
                      {formatToolResult(tc.result)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
