"use client";

/**
 * UnifiedChatPanel — single chat view backed by a strategy.
 *
 * Every conversation is 1:1 with a strategy. The backend determines
 * planning vs execution behavior based on context; the frontend always
 * sends execute mode with a strategyId.
 *
 * Composed from:
 * - `useUnifiedChatModels` — model catalog, selection, reasoning effort
 * - `useChatStreaming` — streaming lifecycle
 * - `useUnifiedChatDataLoading` — session data loading
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { usePrevious } from "@/lib/hooks/usePrevious";
import type {
  ChatMode,
  Message,
  StrategyPlan,
  ToolCall,
  StrategyWithMeta,
} from "@pathfinder/shared";
import {
  APIError,
  getStrategy,
  updateStrategy as updateStrategyApi,
} from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/useStrategyStore";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import { useChatStreaming } from "@/features/chat/hooks/useChatStreaming";
import { useUnifiedChatModels } from "@/features/chat/hooks/useUnifiedChatModels";
import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import { MessageComposer } from "@/features/chat/components/MessageComposer";
import { DraftSelectionBar } from "@/features/chat/components/delegation/DraftSelectionBar";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { useChatPreviewUpdate } from "@/features/chat/hooks/useChatPreviewUpdate";
import { useChatAutoScroll } from "@/features/chat/hooks/useChatAutoScroll";
import { useConsumePendingAskNode } from "@/features/chat/hooks/useConsumePendingAskNode";
import { useResetOnStrategyChange } from "@/features/chat/hooks/useResetOnStrategyChange";
import { parseToolArguments } from "@/features/chat/utils/parseToolArguments";
import { parseToolResult } from "@/features/chat/utils/parseToolResult";
import { useGraphSnapshot } from "@/features/chat/hooks/useGraphSnapshot";
import { useUnifiedChatDataLoading } from "@/features/chat/hooks/useUnifiedChatDataLoading";
import { useUnifiedChatStreamingArgs } from "@/features/chat/components/unifiedChatStreamingArgs";
import { attachThinkingToLastAssistant } from "@/features/chat/utils/attachThinkingToLastAssistant";
import { X } from "lucide-react";

interface UnifiedChatPanelProps {
  siteId: string;
  pendingAskNode?: Record<string, unknown> | null;
  onConsumeAskNode?: () => void;
}

export function UnifiedChatPanel({
  siteId,
  pendingAskNode = null,
  onConsumeAskNode,
}: UnifiedChatPanelProps) {
  // --- Global state ---
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyIdGlobal = useSessionStore((s) => s.setStrategyId);
  const setAuthToken = useSessionStore((s) => s.setAuthToken);
  const setChatIsStreaming = useSessionStore((s) => s.setChatIsStreaming);
  const selectedSiteDisplayName = useSessionStore((s) => s.selectedSiteDisplayName);
  const veupathdbName = useSessionStore((s) => s.veupathdbName);

  // Always execute mode — the backend auto-determines planning vs execution
  // based on strategy context. Every conversation is backed by a strategy.
  const chatMode: ChatMode = "execute";
  const firstName = veupathdbName?.split(" ")[0];
  const displayName = selectedSiteDisplayName || siteId;

  // --- Model management ---
  const models = useUnifiedChatModels();

  // --- Local state ---
  const [messages, setMessages] = useState<Message[]>([]);
  const [apiError, setApiError] = useState<string | null>(null);
  const [draftSelection, setDraftSelection] = useState<Record<string, unknown> | null>(
    null,
  );
  const [undoSnapshots, setUndoSnapshots] = useState<Record<number, StrategyWithMeta>>(
    {},
  );

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

  // --- Strategy store ---
  const addStep = useStrategyStore((s) => s.addStep);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const setWdkInfo = useStrategyStore((s) => s.setWdkInfo);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const clearStrategy = useStrategyStore((s) => s.clear);
  const stepsById = useStrategyStore((s) => s.stepsById);
  const addStrategy = useStrategyListStore((s) => s.addStrategy);
  const addExecutedStrategy = useStrategyListStore((s) => s.addExecutedStrategy);

  // --- Error handling ---
  const handleError = useCallback(
    (error: unknown, fallback: string) => {
      const isUnauthorized =
        error instanceof APIError
          ? error.status === 401
          : error instanceof Error && /HTTP 401\b/.test(error.message);
      if (isUnauthorized) {
        setAuthToken(null);
        setStrategyIdGlobal(null);
        setMessages([]);
        setChatIsStreaming(false);
        setApiError("Session expired. Please sign in again.");
        return;
      }
      setApiError(toUserMessage(error, fallback));
    },
    [setAuthToken, setStrategyIdGlobal, setChatIsStreaming],
  );

  // --- Graph loading ---
  const loadGraph = useCallback(
    (graphId: string) => {
      if (!graphId) return;
      getStrategy(graphId)
        .then((full) => {
          if (sessionRef.current?.snapshotApplied) return;
          setStrategy(full);
          setStrategyMeta({
            name: full.name,
            recordType: full.recordType ?? undefined,
            siteId: full.siteId,
          });
        })
        .catch((err) => {
          console.warn("[UnifiedChat] Failed to load graph:", err);
        });
    },
    [setStrategy, setStrategyMeta],
  );

  const handleAttachThinking = useCallback(
    (
      calls: ToolCall[],
      activity?: {
        calls: Record<string, ToolCall[]>;
        status: Record<string, string>;
      },
    ) => {
      setMessages((prev) => attachThinkingToLastAssistant(prev, calls, activity));
    },
    [],
  );

  const { applyGraphSnapshot } = useGraphSnapshot({
    siteId,
    strategyId,
    stepsById,
    sessionRef,
    setStrategy,
    setStrategyMeta,
  });

  // --- Streaming ---
  const streamingArgs = useUnifiedChatStreamingArgs({
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
    setStrategyIdGlobal,
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
    currentModelSelection: models.currentModelSelection,
    setChatIsStreaming,
    handleError,
  });

  const {
    handleSendMessage: handleSendRaw,
    stopStreaming,
    isStreaming,
    setIsStreaming,
    optimizationProgress,
  } = useChatStreaming(streamingArgs);

  // Sync streaming state globally
  useEffect(() => {
    setChatIsStreaming(isStreaming);
  }, [isStreaming, setChatIsStreaming]);

  const onSend = useCallback(
    async (content: string, mentions?: import("@pathfinder/shared").ChatMention[]) => {
      setChatIsStreaming(true);
      setApiError(null);
      await handleSendRaw(content, mentions);
    },
    [handleSendRaw, setChatIsStreaming],
  );

  // --- Data loading ---
  useUnifiedChatDataLoading({
    chatMode,
    planSessionId: null,
    strategyId,
    isStreaming: isStreaming,
    sessionRef,
    setMessages,
    setSessionArtifacts: () => {},
    setApiError,
    setSelectedModelId: models.setSelectedModelId,
    thinking,
    handleError,
    loadGraph,
  });

  // --- Feature hooks ---
  useChatPreviewUpdate(strategyId, `${messages.length}`);

  useResetOnStrategyChange({
    strategyId,
    previousStrategyId,
    isStreaming: isStreaming,
    resetThinking: thinking.reset,
    setIsStreaming: setIsStreaming,
    setMessages,
    setUndoSnapshots,
    sessionRef,
    stopStreaming: stopStreaming,
  });

  useChatAutoScroll(messagesEndRef, `${messages.length}:${isStreaming ? "s" : "i"}`);

  useConsumePendingAskNode({
    enabled: true,
    pendingAskNode,
    setDraftSelection,
    onConsumeAskNode,
  });

  // --- Render ---
  return (
    <div className="flex h-full flex-col bg-card text-sm">
      <ChatMessageList
        isCompact={false}
        siteId={siteId}
        displayName={displayName}
        firstName={firstName}
        mode={chatMode}
        isStreaming={isStreaming}
        messages={messages}
        undoSnapshots={undoSnapshots}
        onSend={onSend}
        onUndoSnapshot={(snapshot) => {
          setStrategy(snapshot);
          setStrategyMeta({
            name: snapshot.name,
            description: snapshot.description ?? undefined,
            recordType: snapshot.recordType ?? undefined,
          });
        }}
        onApplyPlanningArtifact={async (artifact) => {
          if (!strategyId) return;
          const proposed = artifact.proposedStrategyPlan;
          if (!proposed || typeof proposed !== "object" || Array.isArray(proposed))
            return;
          try {
            await updateStrategyApi(strategyId, {
              plan: proposed as StrategyPlan,
            });
            const full = await getStrategy(strategyId);
            setStrategy(full);
            setStrategyMeta({
              name: full.name,
              description: full.description ?? undefined,
              recordType: full.recordType ?? undefined,
              siteId: full.siteId,
            });
          } catch (err) {
            console.warn("[UnifiedChat] Failed to apply planning artifact:", err);
          }
        }}
        thinking={thinking}
        optimizationProgress={optimizationProgress}
        onCancelOptimization={stopStreaming}
        messagesEndRef={messagesEndRef}
      />

      <div className="border-t border-border bg-card p-3">
        {apiError && (
          <div
            role="alert"
            aria-live="assertive"
            className="mb-3 flex items-start justify-between gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          >
            <p>{apiError}</p>
            <button
              type="button"
              onClick={() => setApiError(null)}
              aria-label="Dismiss error"
              className="shrink-0 rounded p-0.5 text-destructive/50 transition-colors hover:text-destructive"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
        )}
        {draftSelection && (
          <DraftSelectionBar
            selection={draftSelection}
            onRemove={() => setDraftSelection(null)}
          />
        )}
        <MessageComposer
          onSend={onSend}
          disabled={isStreaming}
          isStreaming={isStreaming}
          onStop={stopStreaming}
          mode={chatMode}
          models={models.modelCatalog}
          selectedModelId={models.selectedModelId}
          onModelChange={models.setSelectedModelId}
          reasoningEffort={models.reasoningEffort}
          onReasoningChange={models.setReasoningEffort}
          serverDefaultModelId={models.catalogDefault}
          siteId={siteId}
        />
      </div>
    </div>
  );
}
