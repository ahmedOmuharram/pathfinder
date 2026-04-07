"use client";

/**
 * Orchestrator hook for UnifiedChatPanel.
 *
 * Composes all sub-hooks (stores, streaming, recovery, feature hooks)
 * and returns only the values/callbacks the JSX layer needs.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ChatMention,
  Message,
  PlanningArtifact,
  Strategy,
} from "@pathfinder/shared";
import type { NodeSelection } from "@/lib/types/nodeSelection";
import { usePrevious } from "@/lib/hooks/usePrevious";
import { getStrategy } from "@/lib/api/strategies";
import { undoTurnAction } from "@/features/chat/hooks/undoTurnAction";
import { applyPlanningArtifactAction } from "@/features/chat/hooks/applyPlanningArtifactAction";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";
import { usePlanStore } from "@/state/usePlanStore";
import { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import { useChatStreaming } from "@/features/chat/hooks/useChatStreaming";
import { useUnifiedChatModels } from "@/features/chat/hooks/useUnifiedChatModels";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { useChatPreviewUpdate } from "@/features/chat/hooks/useChatPreviewUpdate";
import { useChatAutoScroll } from "@/features/chat/hooks/useChatAutoScroll";
import { useConsumePendingAskNode } from "@/features/chat/hooks/useConsumePendingAskNode";
import { useResetOnStrategyChange } from "@/features/chat/hooks/useResetOnStrategyChange";
import { parseToolArguments } from "@/features/chat/utils/parseToolArguments";
import { parseToolResult } from "@/features/chat/utils/parseToolResult";
import { useGraphSnapshot } from "@/features/chat/hooks/useGraphSnapshot";
import { useUnifiedChatDataLoading } from "@/features/chat/hooks/useUnifiedChatDataLoading";
import { useOperationRecovery } from "@/features/chat/hooks/useOperationRecovery";
import { useWorkbenchBridge } from "@/lib/hooks/useWorkbenchBridge";
import { useChatErrorHandling } from "@/features/chat/hooks/useChatErrorHandling";
import { useChatStrategyActions } from "@/features/chat/hooks/useChatStrategyActions";

interface UseChatPanelStateArgs {
  siteId: string;
  pendingAskNode?: NodeSelection | null;
  onConsumeAskNode?: () => void;
}

export function useChatPanelState({
  siteId,
  pendingAskNode = null,
  onConsumeAskNode,
}: UseChatPanelStateArgs) {
  // --- Global state ---
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyIdGlobal = useSessionStore((s) => s.setStrategyId);
  const setChatIsStreaming = useSessionStore((s) => s.setChatIsStreaming);
  const selectedSiteDisplayName = useSessionStore((s) => s.selectedSiteDisplayName);
  const veupathdbName = useSessionStore((s) => s.veupathdbName);

  const firstName = veupathdbName?.split(" ")[0];
  const displayName = selectedSiteDisplayName || siteId;

  // --- Model management ---
  const models = useUnifiedChatModels();

  // --- Local state ---
  const [messages, setMessages] = useState<Message[]>([]);
  const [draftSelection, setDraftSelection] = useState<NodeSelection | null>(null);
  const [undoSnapshots, setUndoSnapshots] = useState<Record<number, Strategy>>({});

  const thinking = useThinkingState();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const previousStrategyId = usePrevious(strategyId);

  // --- Session ref ---
  const currentStrategy = useStrategyStore((s) => s.strategy);
  const sessionRef = useRef<StreamingSession | null>(null);

  useEffect(() => {
    if (sessionRef.current) sessionRef.current.latestStrategy = currentStrategy;
  }, [currentStrategy]);

  const createSession = useCallback(
    () => new StreamingSession(currentStrategy),
    [currentStrategy],
  );

  // --- Workbench bridge ---
  const { handleWorkbenchGeneSet } = useWorkbenchBridge();

  const clearMessages = useCallback(() => setMessages([]), []);
  const { handleError, apiError, setApiError } = useChatErrorHandling(
    setStrategyIdGlobal,
    clearMessages,
    setChatIsStreaming,
  );

  const {
    addStep,
    setStrategy,
    setWdkInfo,
    setStrategyMeta,
    clearStrategy,
    stepsById,
    addStrategy,
    addExecutedStrategy,
    loadGraph,
    handleAttachThinking,
  } = useChatStrategyActions(sessionRef, setMessages);

  const { applyGraphSnapshot } = useGraphSnapshot({
    siteId,
    strategyId,
    stepsById,
    sessionRef,
    setStrategy,
    setStrategyMeta,
  });

  // --- Streaming ---
  const {
    handleSendMessage: handleSendRaw,
    stopStreaming,
    isStreaming,
    setIsStreaming,
    optimizationProgress,
    setOptimizationProgress,
  } = useChatStreaming({
    siteId,
    strategyId,
    draftSelection,
    setDraftSelection,
    thinking,
    setMessages,
    setUndoSnapshots,
    sessionRef,
    createSession,
    loadGraph,
    addStrategy,
    addExecutedStrategy,
    setStrategyId: setStrategyIdGlobal,
    setWdkInfo,
    setStrategy,
    setStrategyMeta,
    clearStrategy,
    addStep,
    parseToolArguments,
    parseToolResult,
    applyGraphSnapshot,
    getStrategy,
    currentStrategy,
    attachThinkingToLastAssistant: handleAttachThinking,
    ...(models.setSelectedModelId != null ? { setSelectedModelId: models.setSelectedModelId } : {}),
    ...(models.currentModelSelection != null ? { modelSelection: models.currentModelSelection } : {}),
    setChatIsStreaming,
    onStreamComplete: () => {},
    onStreamError: (error: Error) => {
      handleError(error, "Unable to reach the API.");
    },
    ...(handleWorkbenchGeneSet != null ? { onWorkbenchGeneSet: handleWorkbenchGeneSet } : {}),
  });

  const onSend = useCallback(
    async (content: string, mentions?: ChatMention[], metadata?: Record<string, unknown>) => {
      setApiError(null);
      await handleSendRaw(content, mentions, metadata);
    },
    [handleSendRaw, setApiError],
  );

  // Register send function with plan store so the right-panel PlanPanel can send messages
  useEffect(() => {
    const { registerSendMessage } = usePlanStore.getState();
    const wrappedSend = (text: string, metadata?: Record<string, unknown>) => {
      void onSend(text, undefined, metadata);
    };
    registerSendMessage(wrappedSend);
    return () => registerSendMessage(() => {});
  }, [onSend]);

  // --- Data loading ---
  const handleStrategyNotFound = useCallback(() => {
    setStrategyIdGlobal(null);
  }, [setStrategyIdGlobal]);

  const { isLoading: isLoadingChat } = useUnifiedChatDataLoading({
    strategyId,
    sessionRef,
    setMessages,
    setApiError,
    setSelectedModelId: models.setSelectedModelId,
    thinking,
    setStrategy,
    setStrategyMeta,
    onStrategyNotFound: handleStrategyNotFound,
  });

  // --- Operation recovery (reconnect to in-flight ops on refresh) ---
  useOperationRecovery({
    strategyId,
    siteId,
    isStreaming,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    thinking,
    currentStrategy,
    setStrategyId: setStrategyIdGlobal,
    addStrategy,
    addExecutedStrategy,
    setWdkInfo,
    setStrategy,
    setStrategyMeta,
    clearStrategy,
    addStep,
    loadGraph,
    parseToolArguments,
    parseToolResult,
    applyGraphSnapshot,
    getStrategy,
    attachThinkingToLastAssistant: handleAttachThinking,
    setSelectedModelId: models.setSelectedModelId,
    onApiError: (msg: string) => handleError(new Error(msg), msg),
    setOptimizationProgress,
    onWorkbenchGeneSet: handleWorkbenchGeneSet,
  });

  // --- Feature hooks ---
  useChatPreviewUpdate(strategyId, `${messages.length}`);

  useResetOnStrategyChange({
    strategyId,
    previousStrategyId,
    resetThinking: thinking.reset,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    sessionRef,
    stopStreaming,
  });

  const { bottomRef, isAtBottom, scrollToBottom } = useChatAutoScroll(
    `${messages.length}:${isStreaming ? "s" : "i"}`,
  );

  useConsumePendingAskNode({
    enabled: true,
    pendingAskNode,
    setDraftSelection,
    ...(onConsumeAskNode != null ? { onConsumeAskNode } : {}),
  });

  // --- Undo handler ---
  const [isUndoing, setIsUndoing] = useState(false);
  const setComposerPrefill = useSessionStore((s) => s.setComposerPrefill);

  const handleUndo = useCallback(
    async (userMessageIndex: number) => {
      if (strategyId == null || isUndoing) return;
      const userMsg = messages[userMessageIndex];
      if (userMsg?.role !== "user") return;

      setIsUndoing(true);
      try {
        await undoTurnAction(strategyId, userMsg, userMessageIndex, {
          setMessages,
          setUndoSnapshots,
          setStrategy,
          setStrategyMeta,
          setComposerPrefill,
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Undo failed. Please try again.";
        setApiError(message);
      } finally {
        setIsUndoing(false);
      }
    },
    [strategyId, messages, isUndoing, setMessages, setUndoSnapshots, setStrategy, setStrategyMeta, setComposerPrefill, setApiError],
  );

  // --- Apply planning artifact handler ---
  const [isApplyingArtifact, setIsApplyingArtifact] = useState(false);

  const handleApplyPlanningArtifact = useCallback(
    async (artifact: PlanningArtifact) => {
      if (strategyId == null || isApplyingArtifact) return;
      setIsApplyingArtifact(true);
      try {
        await applyPlanningArtifactAction(strategyId, artifact, {
          setStrategy,
          setStrategyMeta,
        });
      } catch (err) {
        console.warn("[UnifiedChat] Failed to apply planning artifact:", err);
      } finally {
        setIsApplyingArtifact(false);
      }
    },
    [strategyId, isApplyingArtifact, setStrategy, setStrategyMeta],
  );

  return {
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
    models,
    messagesEndRef,
    bottomRef,
    isAtBottom,
    scrollToBottom,
    handleUndo,
    handleApplyPlanningArtifact,
    isApplyingArtifact,
  };
}
