import { useState } from "react";
import type {
  AssistantMessage,
  Message,
  ToolCall,
  PlanningArtifact,
  OptimizationProgressData,
  Strategy,
  UserMessage,
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
  onRegenerate?: (
    userMessage: UserMessage,
    assistantMessage: AssistantMessage,
  ) => void;
  isApplyingArtifact?: boolean;
  onApplyPlanningArtifact?: (artifact: PlanningArtifact) => void;
  thinking: {
    activeMessageId: string | null;
    activeToolCalls: ToolCall[];
    lastToolCalls: ToolCall[];
    reasoning?: string | null;
    getThinkingForMessage: (messageId?: string | null) => {
      activeToolCalls: ToolCall[];
      lastToolCalls: ToolCall[];
      reasoning?: string | null;
    };
  };
  optimizationProgress?: OptimizationProgressData | null;
  onCancelOptimization?: () => void;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  /** Sentinel ref for auto-scroll IntersectionObserver. */
  bottomRef?: ((node: HTMLDivElement | null) => void) | React.RefObject<HTMLDivElement | null>;
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
  onRegenerate,
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
  const activePlanTraceId = usePlanStore((s) => s.activePlanTraceId);
  const activePlanMessageGroupId = usePlanStore((s) => s.activePlanMessageGroupId);
  const isPlanPinned = usePlanStore((s) => s.isPlanPinned);
  const submitPlanAction = usePlanStore((s) => s.submitPlanAction);

  const lastAssistantIndex = (() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i]?.role === "assistant") return i;
    }
    return -1;
  })();

  const activeAssistantIndex = (() => {
    if (!isStreaming) return -1;
    if (thinking.activeMessageId != null && thinking.activeMessageId !== "") {
      for (let i = messages.length - 1; i >= 0; i -= 1) {
        const message = messages[i];
        if (message?.role !== "assistant") continue;
        if (message.messageId === thinking.activeMessageId) return i;
      }
      return -1;
    }
    if (messages[messages.length - 1]?.role === "assistant") {
      return lastAssistantIndex;
    }
    return -1;
  })();

  // True when streaming has started but no assistant message for *this* turn
  // has been created yet (tools/reasoning are running before the model responds).
  const currentTurnHasNoAssistant = isStreaming && activeAssistantIndex === -1;

  // Floating indicator: only when streaming and no assistant message is at the tail yet.
  const showFloatingThinking = currentTurnHasNoAssistant;
  const floatingThinking = thinking.getThinkingForMessage(thinking.activeMessageId);

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
              if (submitPlanAction == null) return;
              void submitPlanAction({
                action: "approve",
                planId: activePlan.id,
                traceId: activePlanTraceId,
                messageGroupId: activePlanMessageGroupId,
                source: "plan_pinned_bar",
              });
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
          const previousUserMessage = (() => {
            for (let i = index - 1; i >= 0; i -= 1) {
              const candidate = messages[i];
              if (candidate?.role === "user") return candidate;
            }
            return null;
          })();
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
            index === activeAssistantIndex;

          if (message.role === "assistant") {
            const effectiveModelId =
              (message.modelId != null && message.modelId !== ""
                ? message.modelId
                : null) ?? message.tokenUsage?.modelId;
            const assistantName =
              catalog.find((m) => m.id === effectiveModelId)?.name ?? "Assistant";
            const liveThinking = thinking.getThinkingForMessage(message.messageId ?? null);
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
                      thinking={liveThinking}
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
                          regenerateDisabled={isStreaming}
                          {...(previousUserMessage != null && onRegenerate != null
                            ? {
                                onRegenerate: () =>
                                  onRegenerate(previousUserMessage, message),
                              }
                            : {})}
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
              activeToolCalls={floatingThinking.activeToolCalls}
              lastToolCalls={floatingThinking.lastToolCalls}
              {...(floatingThinking.reasoning != null
                ? { reasoning: floatingThinking.reasoning }
                : {})}
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
