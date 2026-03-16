"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import type { ToolCall, SubKaniTokenUsage } from "@pathfinder/shared";
import type { DelegateSummary } from "@/features/chat/utils/extractDelegateSummaries";
import { ProviderIcon } from "@/lib/components/ProviderIcon";
import { useSettingsStore } from "@/state/useSettingsStore";
import { formatCompact, formatCost } from "@/lib/utils/format";
import { SubKaniStatusIcon } from "./SubKaniStatusIcon";

interface SubAgentCardProps {
  task: string;
  toolCalls: ToolCall[];
  status: string;
  modelId?: string;
  tokenUsage?: SubKaniTokenUsage;
  instructions?: string;
  steps?: DelegateSummary["steps"];
  notes?: string;
  isLive?: boolean;
}

function borderColor(status: string): string {
  const s = status.toLowerCase();
  if (s.includes("run")) return "border-blue-500";
  if (s.includes("no_step") || s.includes("no step")) return "border-amber-500";
  if (s.includes("timeout") || s.includes("error") || s.includes("fail"))
    return "border-red-500";
  return "border-emerald-500";
}

export function SubAgentCard({
  task,
  toolCalls,
  status,
  modelId,
  tokenUsage,
  instructions,
  steps,
  notes,
  isLive = false,
}: SubAgentCardProps) {
  const [expanded, setExpanded] = useState(false);
  const catalog = useSettingsStore((s) => s.modelCatalog);
  const entry = modelId ? catalog.find((m) => m.id === modelId) : undefined;

  const taskFirstLine = (task.split("\n")[0] ?? task).slice(0, 120);
  const taskTruncated = taskFirstLine.length < task.split("\n")[0]!.length;

  const totalTokens = tokenUsage
    ? tokenUsage.promptTokens + tokenUsage.completionTokens
    : 0;

  const canExpand = !isLive;

  return (
    <div
      className={`rounded-lg border-l-3 bg-muted/30 ${borderColor(status)} ${
        canExpand ? "cursor-pointer" : ""
      }`}
      onClick={canExpand ? () => setExpanded((prev) => !prev) : undefined}
      role={canExpand ? "button" : undefined}
      tabIndex={canExpand ? 0 : undefined}
      onKeyDown={
        canExpand
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setExpanded((prev) => !prev);
              }
            }
          : undefined
      }
    >
      <div className="px-3 py-2 space-y-1.5">
        {/* Row 1: Model + badge + status */}
        <div className="flex items-center gap-2">
          {entry ? (
            <ProviderIcon provider={entry.provider} size={16} />
          ) : (
            <Sparkles className="h-4 w-4 text-muted-foreground" />
          )}
          <span className="text-xs font-medium text-foreground">
            {entry?.name ?? "Sub-agent"}
          </span>
          <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium leading-none text-muted-foreground">
            sub-agent
          </span>
          <span className="ml-auto">
            <SubKaniStatusIcon status={status} className="h-3.5 w-3.5" />
          </span>
        </div>

        {/* Row 2: Task description */}
        <div className="text-xs text-foreground leading-snug">
          {taskFirstLine}
          {taskTruncated && "..."}
        </div>

        {/* Row 3: Step output chips */}
        {steps && steps.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {steps.map((step, idx) => (
              <span
                key={`${step.stepId ?? idx}`}
                className="inline-flex items-center gap-0.5 rounded-md bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground"
              >
                <span aria-hidden="true">&rarr;</span>{" "}
                {step.displayName ?? step.searchName ?? "Step"}
                {step.recordType && (
                  <span className="text-muted-foreground/70">
                    {" "}
                    &middot; {step.recordType}
                  </span>
                )}
              </span>
            ))}
          </div>
        )}

        {/* Row 4: Summary */}
        <div className="text-[11px] text-muted-foreground">
          {toolCalls.length} tool call{toolCalls.length !== 1 ? "s" : ""}
          {tokenUsage && totalTokens > 0 && (
            <>
              {" "}
              &middot; {formatCompact(totalTokens)} tokens &middot; ~
              {formatCost(tokenUsage.estimatedCostUsd)}
            </>
          )}
        </div>
      </div>

      {/* Expanded section */}
      {expanded && !isLive && (
        <div
          className="border-t border-border px-3 py-2 space-y-2"
          onClick={(e) => e.stopPropagation()}
        >
          {instructions && (
            <div className="rounded-md border-l-2 border-muted-foreground/30 bg-muted/50 px-2 py-1.5 text-xs text-muted-foreground italic">
              {instructions}
            </div>
          )}

          {notes && (
            <div className="text-[11px] text-muted-foreground">Notes: {notes}</div>
          )}

          {/* Tool call chain */}
          {toolCalls.length > 0 && (
            <div className="rounded-md bg-muted px-2 py-1 font-mono text-[11px] text-foreground">
              {toolCalls.map((tc) => tc.name).join(" \u2192 ")}
            </div>
          )}

          {/* Individual tool calls */}
          {toolCalls.map((tc) => (
            <details key={tc.id} className="text-xs">
              <summary className="cursor-pointer font-mono text-foreground hover:text-foreground/80">
                {tc.name}
              </summary>
              <pre className="mt-1 max-h-40 overflow-auto rounded bg-muted p-2 text-[11px] text-foreground whitespace-pre-wrap break-words">
                {JSON.stringify(tc.arguments, null, 2)}
              </pre>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
