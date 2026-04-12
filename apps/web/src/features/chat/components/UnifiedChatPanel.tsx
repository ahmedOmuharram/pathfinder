"use client";

/**
 * UnifiedChatPanel — single chat view backed by a strategy.
 *
 * Every conversation is 1:1 with a strategy. The backend determines
 * planning vs execution behavior based on context; the frontend always
 * sends execute mode with a strategyId.
 *
 * All state orchestration lives in `useChatPanelState`.
 * The component is a thin render shell over ChatMessageList + ChatInputBar.
 */

import type { NodeSelection } from "@/lib/types/nodeSelection";
import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import { ChatInputBar } from "@/features/chat/components/ChatInputBar";
import { useChatPanelState } from "@/features/chat/hooks/useChatPanelState";
import { useSessionStore } from "@/state/useSessionStore";

interface UnifiedChatPanelProps {
  siteId: string;
  pendingAskNode?: NodeSelection | null;
  onConsumeAskNode?: () => void;
  onOpenEngine?: (() => void) | undefined;
}

export function UnifiedChatPanel({
  siteId,
  pendingAskNode = null,
  onConsumeAskNode,
  onOpenEngine,
}: UnifiedChatPanelProps) {
  const veupathdbName = useSessionStore((s) => s.veupathdbName);

  const {
    displayName,
    firstName,
    messages,
    undoSnapshots,
    isUndoing,
    isStreaming,
    isLoadingChat,
    onSend,
    stopStreaming,
    optimizationProgress,
    thinking,
    apiError,
    setApiError,
    draftSelection,
    setDraftSelection,
    messagesEndRef,
    bottomRef,
    isAtBottom,
    scrollToBottom,
    handleUndo,
    handleRegenerateTurn,
    handleApplyPlanningArtifact,
    isApplyingArtifact,
  } = useChatPanelState({
    siteId,
    pendingAskNode,
    ...(onConsumeAskNode != null ? { onConsumeAskNode } : {}),
  });

  return (
    <div className="flex h-full flex-col bg-card text-sm">
      <ChatMessageList
        isCompact={false}
        siteId={siteId}
        displayName={displayName}
        {...(firstName != null ? { firstName } : {})}
        {...(veupathdbName != null ? { fullName: veupathdbName } : {})}
        isStreaming={isStreaming}
        isLoading={isLoadingChat}
        messages={messages}
        undoSnapshots={undoSnapshots}
        isUndoing={isUndoing}
        onSend={(content: string, metadata?: Record<string, unknown>) => {
          void onSend(content, undefined, metadata);
        }}
        onUndo={(userMessageIndex: number) => {
          void handleUndo(userMessageIndex);
        }}
        onRegenerate={(userMessage, assistantMessage) => {
          void handleRegenerateTurn(userMessage, assistantMessage);
        }}
        isApplyingArtifact={isApplyingArtifact}
        onApplyPlanningArtifact={(artifact) => {
          void handleApplyPlanningArtifact(artifact);
        }}
        thinking={thinking}
        optimizationProgress={optimizationProgress}
        onCancelOptimization={stopStreaming}
        messagesEndRef={messagesEndRef}
        bottomRef={bottomRef}
        isAtBottom={isAtBottom}
        scrollToBottom={scrollToBottom}
      />

      <ChatInputBar
        apiError={apiError}
        onDismissError={() => setApiError(null)}
        draftSelection={draftSelection}
        onRemoveDraft={() => setDraftSelection(null)}
        onSend={(msg: string, mentions) => {
          void onSend(msg, mentions);
        }}
        isStreaming={isStreaming}
        onStop={stopStreaming}
        onOpenEngine={onOpenEngine}
        siteId={siteId}
      />
    </div>
  );
}
