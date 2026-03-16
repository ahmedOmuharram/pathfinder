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
  /** Workbench store bindings — injected by page to avoid cross-feature import. */
  addGeneSet: (gs: import("@pathfinder/shared").GeneSet) => void;
  geneSets: import("@pathfinder/shared").GeneSet[];
}

export function UnifiedChatPanel({
  siteId,
  pendingAskNode = null,
  onConsumeAskNode,
  addGeneSet,
  geneSets,
}: UnifiedChatPanelProps) {
  const veupathdbName = useSessionStore((s) => s.veupathdbName);

  const {
    displayName,
    firstName,
    messages,
    undoSnapshots,
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
    models,
    messagesEndRef,
    handleUndoSnapshot,
    handleApplyPlanningArtifact,
  } = useChatPanelState({
    siteId,
    pendingAskNode,
    onConsumeAskNode,
    addGeneSet,
    geneSets,
  });

  return (
    <div className="flex h-full flex-col bg-card text-sm">
      <ChatMessageList
        isCompact={false}
        siteId={siteId}
        displayName={displayName}
        firstName={firstName}
        fullName={veupathdbName ?? undefined}
        isStreaming={isStreaming}
        isLoading={isLoadingChat}
        messages={messages}
        undoSnapshots={undoSnapshots}
        onSend={onSend}
        onUndoSnapshot={handleUndoSnapshot}
        onApplyPlanningArtifact={handleApplyPlanningArtifact}
        thinking={thinking}
        optimizationProgress={optimizationProgress}
        onCancelOptimization={stopStreaming}
        messagesEndRef={messagesEndRef}
      />

      <ChatInputBar
        apiError={apiError}
        onDismissError={() => setApiError(null)}
        draftSelection={draftSelection}
        onRemoveDraft={() => setDraftSelection(null)}
        onSend={onSend}
        isStreaming={isStreaming}
        onStop={stopStreaming}
        models={models.modelCatalog}
        selectedModelId={models.selectedModelId}
        onModelChange={models.setSelectedModelId}
        reasoningEffort={models.reasoningEffort}
        onReasoningChange={models.setReasoningEffort}
        serverDefaultModelId={models.catalogDefault}
        siteId={siteId}
      />
    </div>
  );
}
