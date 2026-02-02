import type { Message, ToolCall } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/types/strategy";
import { decodeNodeSelection } from "@/features/chat/node_selection";
import { extractDelegateSummaries } from "@/features/chat/utils/extractDelegateSummaries";
import { ChatEmptyState } from "@/features/chat/components/ChatEmptyState";
import { NodeCard } from "@/features/chat/components/NodeCard";
import { ChatMarkdown } from "@/features/chat/components/ChatMarkdown";
import { ChatThinkingDetails } from "@/features/chat/components/ChatThinkingDetails";
import { ThinkingPanel } from "@/features/chat/components/ThinkingPanel";

interface ChatMessageListProps {
  isCompact: boolean;
  siteId: string;
  displayName: string;
  firstName?: string;
  signedIn: boolean;
  isStreaming: boolean;
  messages: Message[];
  undoSnapshots: Record<number, StrategyWithMeta>;
  onSend: (content: string) => void;
  onUndoSnapshot: (snapshot: StrategyWithMeta) => void;
  thinking: {
    activeToolCalls: ToolCall[];
    lastToolCalls: ToolCall[];
    subKaniCalls: Record<string, ToolCall[]>;
    subKaniStatus: Record<string, string>;
  };
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
}

export function ChatMessageList({
  isCompact,
  siteId,
  displayName,
  firstName,
  signedIn,
  isStreaming,
  messages,
  undoSnapshots,
  onSend,
  onUndoSnapshot,
  thinking,
  messagesEndRef,
}: ChatMessageListProps) {
  return (
    <div className="relative flex-1 min-h-0">
      <div
        className={`chat-messages h-full min-h-0 space-y-1 overflow-y-auto ${
          isCompact ? "p-2" : "p-4"
        }`}
      >
        <ChatEmptyState
          isCompact={isCompact}
          siteId={siteId}
          displayName={displayName}
          firstName={firstName}
          signedIn={signedIn}
          onSend={onSend}
          isStreaming={isStreaming}
          hasMessages={messages.length > 0}
        />

        {messages.map((message, index) => {
          const decoded =
            message.role === "user"
              ? decodeNodeSelection(message.content)
              : { selection: null, message: message.content };
          const nodeData = decoded.selection;
          const hasText = decoded.message && decoded.message.length > 0;
          const delegateSummary =
            message.role === "assistant" && message.toolCalls
              ? extractDelegateSummaries(message.toolCalls)
              : { summaries: [], rejected: [] };
          const subKaniActivity =
            message.role === "assistant" ? message.subKaniActivity : undefined;
          const undoSnapshot = undoSnapshots[index];
          const nodeList = Array.isArray(nodeData?.nodes) ? nodeData.nodes : [];
          const nodeIds = Array.isArray(nodeData?.nodeIds) ? nodeData.nodeIds : [];
          return (
            <div
              key={index}
              className={`flex ${
                message.role === "user" ? "justify-end" : "justify-start"
              } animate-fade-in`}
            >
              {nodeData ? (
                <div className="flex max-w-[85%] flex-col items-end gap-1">
                  <div className="flex w-full gap-2 overflow-x-auto pb-1">
                    {nodeList.map((node, nodeIndex) => (
                      <div
                        key={`${nodeIds[nodeIndex] || nodeIndex}`}
                        className="shrink-0 min-w-[220px]"
                      >
                        <NodeCard node={node} />
                      </div>
                    ))}
                  </div>
                  {hasText && (
                    <div className="rounded-lg bg-slate-900 px-3 py-2 text-white">
                      <ChatMarkdown content={decoded.message} tone="onDark" />
                    </div>
                  )}
                  {message.role === "assistant" && undoSnapshot && (
                    <div className="flex w-full justify-start">
                      <button
                        type="button"
                        onClick={() => onUndoSnapshot(undoSnapshot)}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                        title="Undo model changes"
                        aria-label="Undo model changes"
                      >
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={2}
                          className="h-3.5 w-3.5"
                        >
                          <path d="M9 14L4 9l5-5" />
                          <path d="M20 20v-5a7 7 0 0 0-7-7H4" />
                        </svg>
                        Undo
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex max-w-[85%] flex-col gap-1">
                  <ChatThinkingDetails
                    toolCalls={message.toolCalls}
                    delegateSummaries={delegateSummary.summaries}
                    delegateRejected={delegateSummary.rejected}
                    subKaniActivity={subKaniActivity}
                  />
                  <div
                    className={`rounded-lg px-3 py-2 ${
                      message.role === "user"
                        ? "bg-slate-900 text-white"
                        : "border border-slate-200 bg-slate-50 text-slate-700"
                    }`}
                  >
                    <ChatMarkdown
                      content={message.content}
                      tone={message.role === "user" ? "onDark" : "default"}
                    />
                  </div>
                  {message.role === "assistant" && undoSnapshot && (
                    <div className="flex justify-start">
                      <button
                        type="button"
                        onClick={() => onUndoSnapshot(undoSnapshot)}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-600 transition-colors hover:border-slate-300 hover:bg-slate-50"
                        title="Undo model changes"
                        aria-label="Undo model changes"
                      >
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={2}
                          className="h-3.5 w-3.5"
                        >
                          <path d="M9 14L4 9l5-5" />
                          <path d="M20 20v-5a7 7 0 0 0-7-7H4" />
                        </svg>
                        Undo
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

        <ThinkingPanel
          isStreaming={isStreaming}
          activeToolCalls={thinking.activeToolCalls}
          lastToolCalls={thinking.lastToolCalls}
          subKaniCalls={thinking.subKaniCalls}
          subKaniStatus={thinking.subKaniStatus}
        />

        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
