"use client";

import { useState } from "react";
import JSON5 from "json5";
import type { ToolCall } from "@pathfinder/shared";
import { CheckCircle2, ChevronDown, LoaderCircle } from "lucide-react";

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

export function ToolCallInspector({
  toolCalls,
  isActive = false,
}: ToolCallInspectorProps) {
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
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {isActive && (
          <LoaderCircle className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
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
              isRunning ? "border-input" : "border-border"
            } bg-card`}
          >
            <button
              onClick={() => setExpanded(expanded === tc.id ? null : tc.id)}
              className="flex w-full items-center px-3 py-2 text-left text-foreground transition-colors hover:bg-accent"
            >
              <div className="flex min-w-0 items-center gap-2">
                {isRunning ? (
                  <span title="Running">
                    <LoaderCircle
                      className="h-4 w-4 animate-spin text-muted-foreground"
                      aria-label="Running"
                    />
                  </span>
                ) : (
                  <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Tool
                  </span>
                )}
                <div className="flex min-w-0 flex-col">
                  <span className="whitespace-normal break-all text-xs font-mono text-foreground">
                    {tc.name}
                  </span>
                  {isRunning && (
                    <span className="text-xs text-muted-foreground">
                      {TOOL_DESCRIPTIONS[tc.name] || "Working..."}
                    </span>
                  )}
                </div>
              </div>
              <div className="ml-auto flex items-center gap-2">
                {hasResult && (
                  <span title="Done">
                    <CheckCircle2 className="h-4 w-4 text-success" aria-label="Done" />
                  </span>
                )}
                {!isRunning && (
                  <ChevronDown
                    className={`h-4 w-4 text-muted-foreground transition-transform ${
                      expanded === tc.id ? "rotate-180" : ""
                    }`}
                    aria-hidden="true"
                  />
                )}
              </div>
            </button>

            {expanded === tc.id && (
              <div className="space-y-2 border-t border-border px-3 py-2">
                {Object.keys(tc.arguments || {}).length > 0 && (
                  <div>
                    <div className="mb-1 text-xs text-muted-foreground">Arguments:</div>
                    <pre className="rounded bg-muted p-2 text-xs text-foreground overflow-x-auto whitespace-pre-wrap break-words">
                      {JSON.stringify(tc.arguments, null, 2)}
                    </pre>
                  </div>
                )}
                {tc.result && (
                  <div>
                    <div className="mb-1 text-xs text-muted-foreground">Result:</div>
                    <pre className="max-h-40 rounded bg-muted p-2 text-xs text-foreground overflow-x-auto whitespace-pre-wrap break-words">
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
