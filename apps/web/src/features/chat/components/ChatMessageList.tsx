import { useState } from "react";
import { FileText, FlaskConical } from "lucide-react";
import type {
  ChatMention,
  Message,
  ToolCall,
  PlanningArtifact,
  OptimizationProgressData,
} from "@pathfinder/shared";
import type { ChatMode } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/features/strategy/types";
import { decodeNodeSelection } from "@/features/chat/node_selection";
import { ChatEmptyState } from "@/features/chat/components/ChatEmptyState";
import { NodeCard } from "@/features/chat/components/NodeCard";
import { ChatMarkdown } from "@/features/chat/components/ChatMarkdown";
import { ThinkingPanel } from "@/features/chat/components/ThinkingPanel";
import { OptimizationProgressPanel } from "@/features/chat/components/OptimizationProgressPanel";
import { AssistantMessageParts } from "@/features/chat/components/AssistantMessageParts";
import { formatMessageTime } from "@/lib/formatTime";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChatMessageListProps {
  isCompact: boolean;
  siteId: string;
  displayName: string;
  firstName?: string;
  signedIn: boolean;
  mode?: ChatMode;
  isStreaming: boolean;
  messages: Message[];
  undoSnapshots: Record<number, StrategyWithMeta>;
  onSend: (content: string) => void;
  onUndoSnapshot: (snapshot: StrategyWithMeta) => void;
  onApplyPlanningArtifact?: (artifact: PlanningArtifact) => void;
  thinking: {
    activeToolCalls: ToolCall[];
    lastToolCalls: ToolCall[];
    subKaniCalls: Record<string, ToolCall[]>;
    subKaniStatus: Record<string, string>;
    reasoning?: string | null;
  };
  optimizationProgress?: OptimizationProgressData | null;
  onCancelOptimization?: () => void;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
}

export function ChatMessageList({
  isCompact,
  siteId,
  displayName,
  firstName,
  signedIn,
  mode = "execute",
  isStreaming,
  messages,
  undoSnapshots,
  onSend,
  onUndoSnapshot,
  onApplyPlanningArtifact,
  thinking,
  optimizationProgress,
  onCancelOptimization,
  messagesEndRef,
}: ChatMessageListProps) {
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [showCitationTags, setShowCitationTags] = useState(false);

  // Find the last assistant message so we can attach live streaming parts to it.
  const lastAssistantIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i]?.role === "assistant") return i;
    }
    return -1;
  })();

  // True when streaming has started but no assistant message for *this* turn
  // has been created yet (tools/reasoning are running before the model responds).
  const currentTurnHasNoAssistant =
    isStreaming &&
    (lastAssistantIndex === -1 || messages[messages.length - 1]?.role !== "assistant");

  // Floating indicator: only when streaming and no assistant message is at the tail yet.
  const showFloatingThinking = currentTurnHasNoAssistant;

  return (
    <div className="relative flex-1 min-h-0">
      <div
        className={`chat-messages h-full min-h-0 space-y-3 overflow-y-auto ${
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
          const undoSnapshot = undoSnapshots[index];
          const nodeList = Array.isArray(nodeData?.nodes) ? nodeData.nodes : [];
          const nodeIds = Array.isArray(nodeData?.nodeIds) ? nodeData.nodeIds : [];
          const messageKey = `${index}-${message.timestamp}`;

          const isLive =
            isStreaming &&
            !currentTurnHasNoAssistant &&
            message.role === "assistant" &&
            index === lastAssistantIndex;

          return (
            <div key={index} className="space-y-2">
              <div
                className={`flex ${
                  message.role === "user" ? "justify-end" : "justify-start"
                } animate-fade-in`}
              >
                {/* ---- Node-card messages (user selections) ---- */}
                {nodeData ? (
                  <div className="flex max-w-[85%] flex-col items-end gap-1">
                    {message.mentions?.length ? (
                      <MentionChips mentions={message.mentions} />
                    ) : null}
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
                      <div className="rounded-lg bg-slate-900 px-3 py-2 text-white selection:bg-white selection:text-slate-900">
                        <ChatMarkdown content={decoded.message} tone="onDark" />
                      </div>
                    )}
                    <MessageTimestamp iso={message.timestamp} align="right" />
                  </div>
                ) : message.role === "assistant" ? (
                  <div className="flex max-w-[85%] flex-col gap-1">
                    <AssistantMessageParts
                      index={index}
                      message={message}
                      messageKey={messageKey}
                      isLive={isLive}
                      thinking={thinking}
                      optimizationProgress={isLive ? optimizationProgress : null}
                      onCancelOptimization={onCancelOptimization}
                      onApplyPlanningArtifact={onApplyPlanningArtifact}
                      expandedSources={expandedSources}
                      setExpandedSources={setExpandedSources}
                      showCitationTags={showCitationTags}
                      setShowCitationTags={setShowCitationTags}
                      undoSnapshot={undoSnapshot}
                      onUndoSnapshot={onUndoSnapshot}
                    />
                    {!isLive && (
                      <MessageTimestamp iso={message.timestamp} align="left" />
                    )}
                  </div>
                ) : (
                  /* ---- Plain user text message ---- */
                  <div className="flex max-w-[85%] flex-col items-end gap-1">
                    {message.mentions?.length ? (
                      <MentionChips mentions={message.mentions} />
                    ) : null}
                    <div className="rounded-lg px-3 py-2 bg-slate-900 text-white selection:bg-white selection:text-slate-900">
                      <ChatMarkdown content={message.content} tone="onDark" />
                    </div>
                    <MessageTimestamp iso={message.timestamp} align="right" />
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Floating indicator: streaming started but no assistant message yet */}
        {showFloatingThinking ? (
          <>
            <ThinkingPanel
              isStreaming={isStreaming}
              activeToolCalls={thinking.activeToolCalls}
              lastToolCalls={thinking.lastToolCalls}
              subKaniCalls={thinking.subKaniCalls}
              subKaniStatus={thinking.subKaniStatus}
              reasoning={thinking.reasoning}
              title="Thinking"
            />
            {optimizationProgress && (
              <OptimizationProgressPanel
                data={optimizationProgress}
                onCancel={onCancelOptimization}
              />
            )}
          </>
        ) : null}

        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}

function MentionChips({ mentions }: { mentions: ChatMention[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {mentions.map((m) => {
        const Icon = m.type === "strategy" ? FileText : FlaskConical;
        return (
          <span
            key={`${m.type}-${m.id}`}
            className="inline-flex items-center gap-1 rounded-md bg-blue-900/40 px-2 py-0.5 text-[10px] font-medium text-blue-200 ring-1 ring-inset ring-blue-700/50"
          >
            <Icon className="h-2.5 w-2.5 shrink-0" />
            {m.displayName}
          </span>
        );
      })}
    </div>
  );
}

function MessageTimestamp({ iso, align }: { iso: string; align: "left" | "right" }) {
  const text = formatMessageTime(iso);
  if (!text) return null;
  return (
    <span
      className={`block text-[10px] leading-none text-slate-400 select-none ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {text}
    </span>
  );
}
