import type { ToolCall } from "@pathfinder/shared";
import { Hourglass } from "lucide-react";
import { ToolCallInspector } from "@/features/chat/components/ToolCallInspector";
import { SubKaniStatusIcon } from "@/features/chat/components/SubKaniStatusIcon";

export function ThinkingPanel(props: {
  isStreaming: boolean;
  activeToolCalls: ToolCall[];
  lastToolCalls: ToolCall[];
  subKaniCalls: Record<string, ToolCall[]>;
  subKaniStatus: Record<string, string>;
  reasoning?: string | null;
  title?: string;
}) {
  const {
    isStreaming,
    activeToolCalls,
    lastToolCalls,
    subKaniCalls,
    subKaniStatus,
    reasoning,
    title,
  } = props;
  const subKaniTasks = Object.keys(subKaniCalls);
  const hasReasoning = Boolean(reasoning && reasoning.trim().length > 0);
  const hasAnyContent =
    hasReasoning ||
    activeToolCalls.length > 0 ||
    lastToolCalls.length > 0 ||
    subKaniTasks.length > 0;
  if (!isStreaming && !hasAnyContent) return null;

  return (
    <div className="flex justify-start animate-fade-in">
      <div className="w-[85%] shrink-0">
        <details
          open
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2"
        >
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-slate-500">
            {title || "Thinking"}
          </summary>
          <div className="mt-2 space-y-3 text-[12px] text-slate-700">
            {reasoning && reasoning.trim().length > 0 && (
              <div className="rounded-md border border-slate-100 bg-white p-2">
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Reasoning
                </div>
                <pre className="whitespace-pre-wrap break-words text-[11px] text-slate-700">
                  {reasoning}
                </pre>
              </div>
            )}
            {activeToolCalls.length > 0 ? (
              <div className="rounded-md border border-slate-100 bg-slate-50 p-2">
                <ToolCallInspector toolCalls={activeToolCalls} isActive />
              </div>
            ) : isStreaming ? (
              <div className="flex items-center gap-2 rounded-md border border-slate-100 bg-slate-50 p-2 text-[11px] text-slate-500">
                <Hourglass className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                <span>
                  {reasoning
                    ? "Waiting for tool calls…"
                    : "Waiting for reasoning or tool calls…"}
                </span>
              </div>
            ) : null}

            {subKaniTasks.length > 0 && (
              <details open className="rounded-md border border-slate-100 bg-white p-2">
                <summary className="cursor-pointer select-none text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Sub-kani Activity{" "}
                  <span className="text-[10px] font-semibold text-slate-400">
                    ({subKaniTasks.length})
                  </span>
                </summary>
                <div className="mt-2 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {Object.entries(subKaniCalls).map(([task, calls]) => (
                    <div
                      key={task}
                      className="min-w-0 rounded-md border border-slate-100 bg-slate-50 p-2"
                    >
                      <div className="mb-1 flex items-start gap-2 text-[11px] font-semibold text-slate-600">
                        <span className="min-w-0 flex-1 whitespace-normal break-words leading-snug">
                          {task}
                        </span>
                        <SubKaniStatusIcon status={subKaniStatus[task] || "running"} />
                      </div>
                      {calls.length > 0 ? (
                        <ToolCallInspector toolCalls={calls} isActive />
                      ) : (
                        <div className="flex items-center gap-2 text-[11px] text-slate-500">
                          <Hourglass
                            className="h-3.5 w-3.5 text-slate-400"
                            aria-hidden="true"
                          />
                          <span>Waiting for sub-kani tool calls…</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </details>
            )}

            {lastToolCalls.length > 0 && (
              <div className="rounded-md border border-slate-100 bg-white p-2">
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Recent Tool Output
                </div>
                <ToolCallInspector toolCalls={lastToolCalls} />
              </div>
            )}
          </div>
        </details>
      </div>
    </div>
  );
}
