import { useState, useEffect } from "react";
import type {
  Message,
  ToolCall,
  PlanningArtifact,
  OptimizationProgressData,
  Strategy,
} from "@pathfinder/shared";
import { decodeNodeSelection } from "@/features/chat/node_selection";
import { ChatEmptyState } from "@/features/chat/components/ChatEmptyState";
import { UserAvatar, AssistantAvatar } from "@/features/chat/components/ChatMessageListAvatars";
import {
  ChatLoadingSkeleton,
  MessageTimestamp,
  UndoButton,
  ScrollToBottomButton,
  UserMessageBody,
} from "@/features/chat/components/ChatMessageListHelpers";
import { ThinkingPanel } from "@/features/chat/components/thinking/ThinkingPanel";
import { OptimizationProgressPanel } from "@/features/chat/components/optimization/OptimizationProgressPanel";
import { PlanPinnedBar } from "@/features/chat/components/plan/PlanPinnedBar";
import { AssistantMessageParts } from "@/features/chat/components/message/AssistantMessageParts";
import { MessageFeedback } from "@/features/chat/components/message/MessageFeedback";
import { TokenUsageDisplay } from "@/features/chat/components/message/TokenUsageDisplay";
import { useModelCatalogQuery } from "@/lib/query/hooks/useModelCatalogQuery";
import { useSessionStore } from "@/state/useSessionStore";
import { usePlanStore } from "@/state/usePlanStore";

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
  isUndoing?: boolean;
  onSend: (content: string, metadata?: Record<string, unknown>) => void;
  onUndo?: (userMessageIndex: number) => void;
  isApplyingArtifact?: boolean;
  onApplyPlanningArtifact?: (artifact: PlanningArtifact) => void;
  thinking: {
    activeToolCalls: ToolCall[];
    lastToolCalls: ToolCall[];
    reasoning?: string | null;
  };
  optimizationProgress?: OptimizationProgressData | null;
  onCancelOptimization?: () => void;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  /** Sentinel ref for auto-scroll IntersectionObserver. */
  bottomRef?: React.RefObject<HTMLDivElement | null>;
  /** Whether the user is scrolled near the bottom. */
  isAtBottom?: boolean;
  /** Scroll to the bottom of the message list. */
  scrollToBottom?: () => void;
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
  isUndoing,
  onSend,
  onUndo,
  isApplyingArtifact = false,
  onApplyPlanningArtifact,
  thinking,
  optimizationProgress,
  onCancelOptimization,
  messagesEndRef,
  bottomRef,
  isAtBottom = true,
  scrollToBottom,
}: ChatMessageListProps) {
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [showCitationTags, setShowCitationTags] = useState(false);
  const { data: catalogData } = useModelCatalogQuery();
  const catalog = catalogData?.models ?? [];
  const strategyId = useSessionStore((s) => s.strategyId);
  const activePlan = usePlanStore((s) => s.activePlan);
  const isPlanPinned = usePlanStore((s) => s.isPlanPinned);

  // Track when the plan card scrolls out of view to show the pinned bar.
  useEffect(() => {
    if (!activePlan) return;
    const card = document.querySelector(`[data-plan-id="${activePlan.id}"]`);
    if (!card) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry) {
          usePlanStore.getState().setPinned(!entry.isIntersecting);
        }
      },
      { threshold: 0.1 },
    );
    observer.observe(card);
    return () => observer.disconnect();
  }, [activePlan]);

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

  const userDisplayName = fullName ?? firstName ?? "User";

  return (
    <div className="relative flex-1 min-h-0">
      <div
        role="log"
        aria-label="Chat messages"
        className={`chat-messages h-full min-h-0 space-y-3 overflow-y-auto ${
          isCompact ? "p-2" : "p-4"
        }`}
      >
        {activePlan && isPlanPinned && activePlan.status === "presented" && (
          <PlanPinnedBar
            plan={activePlan}
            onApprove={() => {
              usePlanStore.getState().updatePlan({ status: "approved" });
            }}
            onViewPlan={() => {
              document
                .querySelector(`[data-plan-id="${activePlan.id}"]`)
                ?.scrollIntoView({ behavior: "smooth" });
            }}
          />
        )}
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
          // Hide plan interaction messages — they are internal control
          // messages (approve, answer_question) that should not render.
          if (
            message.role === "user" &&
            message.content.startsWith("[Plan interaction:")
          ) {
            return null;
          }

          const decoded =
            message.role === "user"
              ? decodeNodeSelection(message.content)
              : { selection: null, message: message.content };
          const nodeData = decoded.selection;
          const hasText = decoded.message.length > 0;
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
            const effectiveModelId =
              (message.modelId != null && message.modelId !== ""
                ? message.modelId
                : null) ?? message.tokenUsage?.modelId;
            const assistantName =
              catalog.find((m) => m.id === effectiveModelId)?.name ?? "Assistant";
            return (
              <div
                key={messageKey}
                data-testid="assistant-message"
                className="group animate-fade-in"
              >
                <div className="flex gap-3">
                  <AssistantAvatar
                    {...(effectiveModelId != null ? { modelId: effectiveModelId } : {})}
                  />
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
                      optimizationProgress={
                        isLive ? (optimizationProgress ?? null) : null
                      }
                      {...(onCancelOptimization != null
                        ? { onCancelOptimization }
                        : {})}
                      isApplyingArtifact={isApplyingArtifact}
                      {...(onApplyPlanningArtifact != null
                        ? { onApplyPlanningArtifact }
                        : {})}
                      onSendMessage={onSend}
                      expandedSources={expandedSources}
                      setExpandedSources={setExpandedSources}
                      showCitationTags={showCitationTags}
                      setShowCitationTags={setShowCitationTags}
                      {...(undoSnapshot != null ? { undoSnapshot } : {})}
                    />
                    {!isLive && (
                      <div className="mt-1.5 flex items-center gap-2">
                        {message.tokenUsage && (
                          <TokenUsageDisplay usage={message.tokenUsage} />
                        )}
                        <MessageTimestamp iso={message.timestamp} />
                        <MessageFeedback
                          traceId={message.traceId ?? null}
                          streamId={strategyId ?? ""}
                        />
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
                  <UserMessageBody
                    nodeData={nodeData}
                    nodeList={nodeList}
                    nodeIds={nodeIds}
                    hasText={hasText}
                    decodedMessage={decoded.message}
                    rawContent={message.content}
                    mentions={message.mentions}
                  />
                  <div className="mt-1.5 flex items-center gap-2">
                    <MessageTimestamp iso={message.timestamp} />
                    {onUndo != null && message.entryId != null && !isStreaming && (
                      <UndoButton
                        onClick={() => onUndo(index)}
                        disabled={isUndoing === true}
                      />
                    )}
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
              {...(thinking.reasoning != null ? { reasoning: thinking.reasoning } : {})}
              title="Thinking"
            />
            {optimizationProgress != null ? (
              <OptimizationProgressPanel
                data={optimizationProgress}
                {...(onCancelOptimization != null
                  ? { onCancel: onCancelOptimization }
                  : {})}
              />
            ) : null}
          </>
        ) : null}

        <div ref={messagesEndRef} />
        {bottomRef != null && <div ref={bottomRef} className="h-px" />}
      </div>

      {/* Floating scroll-to-bottom button */}
      {!isAtBottom && isStreaming && scrollToBottom !== undefined && (
        <ScrollToBottomButton onClick={scrollToBottom} />
      )}
    </div>
  );
}

