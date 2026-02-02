import type { ToolCall } from "@pathfinder/shared";
import { ToolCallInspector } from "@/features/chat/components/ToolCallInspector";

export function ThinkingPanel(props: {
  isStreaming: boolean;
  activeToolCalls: ToolCall[];
  lastToolCalls: ToolCall[];
  subKaniCalls: Record<string, ToolCall[]>;
  subKaniStatus: Record<string, string>;
}) {
  const { isStreaming, activeToolCalls, lastToolCalls, subKaniCalls, subKaniStatus } = props;
  if (!isStreaming) return null;

  return (
    <div className="flex justify-start animate-fade-in">
      <div className="max-w-[85%]">
        <details open className="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-slate-500">
            Thinking
          </summary>
          <div className="mt-2 space-y-3 text-[12px] text-slate-700">
            {activeToolCalls.length > 0 ? (
              <div className="rounded-md border border-slate-100 bg-slate-50 p-2">
                <ToolCallInspector toolCalls={activeToolCalls} isActive />
              </div>
            ) : (
              <div className="rounded-md border border-slate-100 bg-slate-50 p-2 text-[11px] text-slate-500">
                Waiting for tool calls...
              </div>
            )}

            {Object.keys(subKaniCalls).length > 0 && (
              <div className="rounded-md border border-slate-100 bg-white p-2">
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Sub-kani Activity
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {Object.entries(subKaniCalls).map(([task, calls]) => (
                    <div
                      key={task}
                      className="min-w-0 rounded-md border border-slate-100 bg-slate-50 p-2"
                    >
                      <div className="mb-1 flex items-center justify-between text-[11px] font-semibold text-slate-600">
                        <span>{task}</span>
                        <span className="uppercase text-[10px] text-slate-400">
                          {subKaniStatus[task] || "running"}
                        </span>
                      </div>
                      {calls.length > 0 ? (
                        <ToolCallInspector toolCalls={calls} isActive />
                      ) : (
                        <div className="text-[11px] text-slate-500">
                          Waiting for sub-kani tool calls...
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
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

