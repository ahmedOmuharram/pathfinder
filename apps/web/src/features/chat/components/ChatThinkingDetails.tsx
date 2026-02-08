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
  title?: string;
}

export function ChatThinkingDetails({
  toolCalls,
  delegateSummaries = [],
  delegateRejected = [],
  subKaniActivity,
  title,
}: ChatThinkingDetailsProps) {
  const hasToolCalls = (toolCalls?.length || 0) > 0;
  const hasSubKaniActivity = Object.keys(subKaniActivity?.calls || {}).length > 0;
  const hasDelegate = delegateSummaries.length > 0 || delegateRejected.length > 0;

  if (!hasToolCalls && !hasSubKaniActivity && !hasDelegate) return null;

  const subKaniTasks = Object.keys(subKaniActivity?.calls || {});

  return (
    <details className="rounded-lg border border-slate-200 bg-white px-3 py-2">
      <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-slate-500">
        {title || "Thinking"}
      </summary>
      <div className="mt-2 space-y-3 text-[12px] text-slate-700">
        {hasToolCalls && (
          <div className="rounded-md border border-slate-100 bg-slate-50 p-2">
            <ToolCallInspector toolCalls={toolCalls || []} />
          </div>
        )}

        {delegateSummaries.length > 0 && (
          <div className="rounded-md border border-slate-100 bg-white p-2">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Sub-kani Outputs
            </div>
            <div className="space-y-2">
              {delegateSummaries.map((summary, idx) => (
                <div
                  key={`${summary.task || "subtask"}-${idx}`}
                  className="rounded-md border border-slate-100 bg-slate-50 p-2"
                >
                  <div className="text-[11px] font-semibold text-slate-600">
                    {summary.task || "Subtask"}
                  </div>
                  {summary.steps.length > 0 ? (
                    <ul className="mt-1 space-y-1 text-[11px] text-slate-600">
                      {summary.steps.map((step, pIdx) => (
                        <li key={`${step.stepId || "step"}-${pIdx}`}>
                          <span className="font-semibold text-slate-700">
                            {step.displayName || step.searchName || "Step"}
                          </span>
                          {step.recordType && (
                            <span className="text-slate-500"> · {step.recordType}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-[11px] text-slate-500">No proposals returned.</div>
                  )}
                  {summary.notes && (
                    <div className="mt-1 text-[11px] text-slate-500">
                      Notes: {summary.notes}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {hasSubKaniActivity && (
          <details open className="rounded-md border border-slate-100 bg-white p-2">
            <summary className="cursor-pointer select-none text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Sub-kani Activity{" "}
              <span className="text-[10px] font-semibold text-slate-400">
                ({subKaniTasks.length})
              </span>
            </summary>
            <div className="mt-2 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {Object.entries(subKaniActivity?.calls || {}).map(([task, calls]) => (
                <div
                  key={task}
                  className="min-w-0 rounded-md border border-slate-100 bg-slate-50 p-2"
                >
                  <div className="mb-1 flex items-start gap-2 text-[11px] font-semibold text-slate-600">
                    <span className="min-w-0 flex-1 whitespace-normal break-words leading-snug">
                      {task}
                    </span>
                    <SubKaniStatusIcon status={subKaniActivity?.status?.[task] || "done"} />
                  </div>
                  {calls.length > 0 ? (
                    <ToolCallInspector toolCalls={calls} />
                  ) : (
                    <div className="flex items-center gap-2 text-[11px] text-slate-500">
                      <Hourglass className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                      <span>No sub-kani tool calls recorded.</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </details>
        )}

        {delegateRejected.length > 0 && (
          <div className="rounded-md border border-slate-100 bg-white p-2">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Rejected Subtasks
            </div>
            <ul className="space-y-1 text-[11px] text-slate-500">
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

