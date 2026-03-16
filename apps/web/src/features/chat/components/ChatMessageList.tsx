import { useState } from "react";
import { FileText, FlaskConical } from "lucide-react";
import type {
  ChatMention,
  Message,
  ToolCall,
  PlanningArtifact,
  OptimizationProgressData,
  Strategy,
} from "@pathfinder/shared";
import { decodeNodeSelection } from "@/features/chat/node_selection";
import { ChatEmptyState } from "@/features/chat/components/ChatEmptyState";
import { NodeCard } from "@/features/chat/components/delegation/NodeCard";
import { ChatMarkdown } from "@/lib/components/ChatMarkdown";
import { ThinkingPanel } from "@/features/chat/components/thinking/ThinkingPanel";
import { OptimizationProgressPanel } from "@/features/chat/components/optimization/OptimizationProgressPanel";
import { AssistantMessageParts } from "@/features/chat/components/message/AssistantMessageParts";
import { TokenUsageDisplay } from "@/features/chat/components/message/TokenUsageDisplay";
import { formatMessageTime } from "@/lib/formatTime";
import { ProviderIcon } from "@/lib/components/ProviderIcon";
import { useSettingsStore } from "@/state/useSettingsStore";

// ---------------------------------------------------------------------------
// Avatars
// ---------------------------------------------------------------------------

function UserAvatar({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <div className="flex-shrink-0 size-7 rounded-full bg-primary flex items-center justify-center text-[11px] font-bold text-primary-foreground">
      {initials}
    </div>
  );
}

function AssistantAvatar({ modelId }: { modelId?: string }) {
  const catalog = useSettingsStore((s) => s.modelCatalog);
  const entry = catalog.find((m) => m.id === modelId);
  const provider = entry?.provider ?? "openai";
  return (
    <div className="flex-shrink-0 size-7 rounded-md bg-muted flex items-center justify-center">
      <ProviderIcon provider={provider} size={16} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChatMessageListProps {
  isCompact: boolean;
  siteId: string;
  displayName: string;
  firstName?: string;
  fullName?: string;
  isStreaming: boolean;
  isLoading?: boolean;
  messages: Message[];
  undoSnapshots: Record<number, Strategy>;
  onSend: (content: string) => void;
  onUndoSnapshot: (snapshot: Strategy) => void;
  onApplyPlanningArtifact?: (artifact: PlanningArtifact) => void;
  thinking: {
    activeToolCalls: ToolCall[];
    lastToolCalls: ToolCall[];
    subKaniCalls: Record<string, ToolCall[]>;
    subKaniStatus: Record<string, string>;
    subKaniModels?: Record<string, string>;
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
  fullName,
  isStreaming,
  isLoading = false,
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
  const catalog = useSettingsStore((s) => s.modelCatalog);

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

  const userDisplayName = fullName || firstName || "User";

  return (
    <div className="relative flex-1 min-h-0">
      <div
        className={`chat-messages h-full min-h-0 space-y-3 overflow-y-auto ${
          isCompact ? "p-2" : "p-4"
        }`}
      >
        {isLoading ? (
          <ChatLoadingSkeleton />
        ) : (
          <ChatEmptyState
            isCompact={isCompact}
            siteId={siteId}
            displayName={displayName}
            firstName={firstName}
            onSend={onSend}
            isStreaming={isStreaming}
            hasMessages={messages.length > 0}
          />
        )}

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

          if (message.role === "assistant") {
            const effectiveModelId = message.modelId || message.tokenUsage?.modelId;
            const assistantName =
              catalog.find((m) => m.id === effectiveModelId)?.name ?? "Assistant";
            return (
              <div
                key={messageKey}
                data-testid="assistant-message"
                className="animate-fade-in"
              >
                <div className="flex gap-3">
                  <AssistantAvatar modelId={effectiveModelId} />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-semibold text-muted-foreground mb-1">
                      {assistantName}
                    </div>
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
                      <div className="mt-1.5">
                        {message.tokenUsage && (
                          <TokenUsageDisplay usage={message.tokenUsage} />
                        )}
                        <MessageTimestamp iso={message.timestamp} />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          }

          // User message (with or without node cards)
          return (
            <div
              key={messageKey}
              data-testid="user-message"
              className="animate-fade-in"
            >
              <div className="flex gap-3">
                <UserAvatar name={userDisplayName} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-muted-foreground mb-1">
                    {userDisplayName}
                  </div>
                  {nodeData ? (
                    <div className="space-y-1">
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
                        <div className="rounded-lg bg-primary px-3 py-2 text-primary-foreground selection:bg-primary-foreground selection:text-primary">
                          <ChatMarkdown content={decoded.message} tone="onDark" />
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-1">
                      {message.mentions?.length ? (
                        <MentionChips mentions={message.mentions} />
                      ) : null}
                      <div className="rounded-lg px-3 py-2 bg-primary text-primary-foreground selection:bg-primary-foreground selection:text-primary">
                        <ChatMarkdown content={message.content} tone="onDark" />
                      </div>
                    </div>
                  )}
                  <div className="mt-1.5">
                    <MessageTimestamp iso={message.timestamp} />
                  </div>
                </div>
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
              subKaniModels={thinking.subKaniModels}
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
            className="inline-flex items-center gap-1 rounded-md bg-primary/15 px-2 py-0.5 text-xs font-medium text-primary-foreground ring-1 ring-inset ring-primary/30"
          >
            <Icon className="h-2.5 w-2.5 shrink-0" />
            {m.displayName}
          </span>
        );
      })}
    </div>
  );
}

function ChatLoadingSkeleton() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 animate-fade-in">
      <div className="flex gap-1.5">
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:0ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:150ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40 [animation-delay:300ms]" />
      </div>
      <p className="text-xs text-muted-foreground">Loading conversation...</p>
    </div>
  );
}

function MessageTimestamp({ iso }: { iso: string }) {
  const text = formatMessageTime(iso);
  if (!text) return null;
  return (
    <span className="mt-2 block text-xs leading-none text-muted-foreground select-none">
      {text}
    </span>
  );
}
