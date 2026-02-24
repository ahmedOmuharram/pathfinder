"use client";

import type { ToolCall } from "@pathfinder/shared";
import { Hourglass } from "lucide-react";
import { ToolCallInspector } from "@/features/chat/components/ToolCallInspector";
import { SubKaniStatusIcon } from "@/features/chat/components/SubKaniStatusIcon";
import type {
  DelegateSummary,
  RejectedDelegateSummary,
} from "@/features/chat/utils/extractDelegateSummaries";

export interface SubKaniActivity {
  calls: Record<string, ToolCall[]>;
  status?: Record<string, string>;
}

interface ChatThinkingDetailsProps {
  toolCalls?: ToolCall[];
  delegateSummaries?: DelegateSummary[];
  delegateRejected?: RejectedDelegateSummary[];
  subKaniActivity?: SubKaniActivity;
  reasoning?: string | null;
  title?: string;
}

export function ChatThinkingDetails({
  toolCalls,
  delegateSummaries = [],
  delegateRejected = [],
  subKaniActivity,
  reasoning,
  title,
}: ChatThinkingDetailsProps) {
  const hasToolCalls = (toolCalls?.length || 0) > 0;
  const hasSubKaniActivity = Object.keys(subKaniActivity?.calls || {}).length > 0;
  const hasDelegate = delegateSummaries.length > 0 || delegateRejected.length > 0;
  const hasReasoning = Boolean(reasoning && reasoning.trim().length > 0);

  if (!hasToolCalls && !hasSubKaniActivity && !hasDelegate && !hasReasoning)
    return null;

  const subKaniTasks = Object.keys(subKaniActivity?.calls || {});

  return (
    <details className="rounded-lg border border-border bg-card px-3 py-2">
      <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title || "Thinking"}
      </summary>
      <div className="mt-2 space-y-3 text-sm text-foreground">
        {hasReasoning && (
          <div className="rounded-md border border-border bg-card p-2">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Reasoning
            </div>
            <pre className="whitespace-pre-wrap break-words text-xs text-foreground">
              {reasoning}
            </pre>
          </div>
        )}
        {hasToolCalls && (
          <div className="rounded-md border border-border bg-muted p-2">
            <ToolCallInspector toolCalls={toolCalls || []} />
          </div>
        )}

        {delegateSummaries.length > 0 && (
          <div className="rounded-md border border-border bg-card p-2">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Sub-kani Outputs
            </div>
            <div className="space-y-2">
              {delegateSummaries.map((summary, idx) => (
                <div
                  key={`${summary.task || "subtask"}-${idx}`}
                  className="rounded-md border border-border bg-muted p-2"
                >
                  <div className="text-xs font-semibold text-muted-foreground">
                    {summary.task || "Subtask"}
                  </div>
                  {summary.steps.length > 0 ? (
                    <ul className="mt-1 space-y-1 text-xs text-muted-foreground">
                      {summary.steps.map((step, pIdx) => (
                        <li key={`${step.stepId || "step"}-${pIdx}`}>
                          <span className="font-semibold text-foreground">
                            {step.displayName || step.searchName || "Step"}
                          </span>
                          {step.recordType && (
                            <span className="text-muted-foreground">
                              {" "}
                              · {step.recordType}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-xs text-muted-foreground">
                      No proposals returned.
                    </div>
                  )}
                  {summary.notes && (
                    <div className="mt-1 text-xs text-muted-foreground">
                      Notes: {summary.notes}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {hasSubKaniActivity && (
          <details open className="rounded-md border border-border bg-card p-2">
            <summary className="cursor-pointer select-none text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Sub-kani Activity{" "}
              <span className="text-xs font-semibold text-muted-foreground">
                ({subKaniTasks.length})
              </span>
            </summary>
            <div className="mt-2 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {Object.entries(subKaniActivity?.calls || {}).map(([task, calls]) => (
                <div
                  key={task}
                  className="min-w-0 rounded-md border border-border bg-muted p-2"
                >
                  <div className="mb-1 flex items-start gap-2 text-xs font-semibold text-muted-foreground">
                    <span className="min-w-0 flex-1 whitespace-normal break-words leading-snug">
                      {task}
                    </span>
                    <SubKaniStatusIcon
                      status={subKaniActivity?.status?.[task] || "done"}
                    />
                  </div>
                  {calls.length > 0 ? (
                    <ToolCallInspector toolCalls={calls} />
                  ) : (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Hourglass
                        className="h-3.5 w-3.5 text-muted-foreground"
                        aria-hidden="true"
                      />
                      <span>No sub-kani tool calls recorded.</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </details>
        )}

        {delegateRejected.length > 0 && (
          <div className="rounded-md border border-border bg-card p-2">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Rejected Subtasks
            </div>
            <ul className="space-y-1 text-xs text-muted-foreground">
              {delegateRejected.map((entry, idx) => (
                <li key={`${entry.task || "rejected"}-${idx}`}>
                  {entry.task || "Subtask"}: {entry.error || "Rejected"}
                  {entry.details && <span> · {entry.details}</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </details>
  );
}
