"use client";

/**
 * UnifiedChatPanel — single chat view for both planning and execution.
 *
 * Mode is **auto-detected**: if a strategy is attached, the panel uses
 * execute mode; otherwise it uses plan mode. There is no user-facing toggle.
 */

import { useCallback, useEffect, useRef, useState, startTransition } from "react";
import { usePrevious } from "@/shared/hooks/usePrevious";
import type {
  ChatMode,
  Message,
  PlanningArtifact,
  ReasoningEffort,
  StrategyPlan,
  ToolCall,
} from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/types/strategy";
import {
  APIError,
  getPlanSession,
  getStrategy,
  listModels,
  openStrategy,
  updatePlanSession,
  updateStrategy as updateStrategyApi,
} from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useSettingsStore } from "@/state/useSettingsStore";
import { useStrategyStore } from "@/state/useStrategyStore";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import { useChatStreaming } from "@/features/chat/hooks/useChatStreaming";
import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import {
  MessageComposer,
  buildModelSelection,
} from "@/features/chat/components/MessageComposer";
import { DraftSelectionBar } from "@/features/chat/components/DraftSelectionBar";
import { upsertSessionArtifact } from "@/features/chat/utils/planStreamState";
import { openAndHydrateDraftStrategy } from "@/features/strategy/services/openAndHydrateDraftStrategy";
import { getDelegationDraft } from "@/features/chat/utils/delegationDraft";
import { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { useChatPreviewUpdate } from "@/features/chat/hooks/useChatPreviewUpdate";
import { useChatAutoScroll } from "@/features/chat/hooks/useChatAutoScroll";
import { useConsumePendingAskNode } from "@/features/chat/hooks/useConsumePendingAskNode";
import { useResetOnStrategyChange } from "@/features/chat/hooks/useResetOnStrategyChange";
import { parseToolArguments } from "@/features/chat/utils/parseToolArguments";
import { parseToolResult } from "@/features/chat/utils/parseToolResult";
import { useGraphSnapshot } from "@/features/chat/hooks/useGraphSnapshot";
import type { ModelCatalogEntry } from "@pathfinder/shared";
import { DelegationDraftViewer } from "@/features/chat/components/DelegationDraftViewer";
import { useUnifiedChatDataLoading } from "@/features/chat/hooks/useUnifiedChatDataLoading";
import { useUnifiedChatStreamingArgs } from "@/features/chat/components/unifiedChatStreamingArgs";

interface UnifiedChatPanelProps {
  siteId: string;
  pendingAskNode?: Record<string, unknown> | null;
  onConsumeAskNode?: () => void;
  onInsertStrategy?: () => void;
  /** Reference strategy ID injected from insert-strategy modal. */
  referenceStrategyId?: string | null;
  /** Clear the reference strategy ID after it's consumed. */
  onConsumeReferenceStrategy?: () => void;
}

export function UnifiedChatPanel({
  siteId,
  pendingAskNode = null,
  onConsumeAskNode,
  onInsertStrategy,
  referenceStrategyId: referenceStrategyIdProp = null,
  onConsumeReferenceStrategy,
}: UnifiedChatPanelProps) {
  // Global state
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyIdGlobal = useSessionStore((s) => s.setStrategyId);
  const planSessionId = useSessionStore((s) => s.planSessionId);
  const setPlanSessionId = useSessionStore((s) => s.setPlanSessionId);
  const setAuthToken = useSessionStore((s) => s.setAuthToken);
  const setChatIsStreaming = useSessionStore((s) => s.setChatIsStreaming);
  const bumpPlanListVersion = useSessionStore((s) => s.bumpPlanListVersion);
  const selectedSiteDisplayName = useSessionStore((s) => s.selectedSiteDisplayName);
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const veupathdbName = useSessionStore((s) => s.veupathdbName);
  const linkConversation = useSessionStore((s) => s.linkConversation);

  const firstName = veupathdbName?.split(" ")[0];
  const displayName = selectedSiteDisplayName || siteId;

  // Derived mode — execute when strategy attached, otherwise plan
  const chatMode: ChatMode = strategyId ? "execute" : "plan";

  // Settings / model state
  const modelCatalog = useSettingsStore((s) => s.modelCatalog);
  const setModelCatalog = useSettingsStore((s) => s.setModelCatalog);
  const catalogDefault = useSettingsStore((s) => s.catalogDefault);
  const defaultModelId = useSettingsStore((s) => s.defaultModelId);
  const defaultReasoningEffort = useSettingsStore((s) => s.defaultReasoningEffort);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningEffort>("medium");

  // Sync from settings store defaults on mount / when defaults change
  useEffect(() => {
    setSelectedModelId(defaultModelId);
  }, [defaultModelId]);
  useEffect(() => {
    setReasoningEffort(defaultReasoningEffort);
  }, [defaultReasoningEffort]);

  // Fetch model catalog on mount
  useEffect(() => {
    listModels()
      .then((res) => setModelCatalog(res.models, res.default))
      .catch((err) => console.warn("[UnifiedChat] Failed to load models:", err));
  }, [setModelCatalog]);

  // Local state
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionArtifacts, setSessionArtifacts] = useState<PlanningArtifact[]>([]);
  const [apiError, setApiError] = useState<string | null>(null);

  const [draftSelection, setDraftSelection] = useState<Record<string, unknown> | null>(
    null,
  );
  const [undoSnapshots, setUndoSnapshots] = useState<Record<number, StrategyWithMeta>>(
    {},
  );

  const thinking = useThinkingState();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [pendingExecutorBuildMessage, setPendingExecutorBuildMessage] = useState<
    string | null
  >(null);
  /** Strategy ID + prompt to auto-execute after the plan→execute transition. */
  const [pendingAutoExecute, setPendingAutoExecute] = useState<{
    strategyId: string;
    prompt: string;
  } | null>(null);
  const executeStrategyId = chatMode === "execute" ? strategyId : null;
  const previousStrategyId = usePrevious(executeStrategyId);

  // Streaming session — encapsulates undo snapshot, applied-snapshot flag, and
  // latest strategy for the duration of a single streaming request.
  const sessionRef = useRef<StreamingSession | null>(null);

  // Strategy store
  const currentStrategy = useStrategyStore((s) => s.strategy);

  // Keep active session's latestStrategy in sync with the store.
  useEffect(() => {
    if (sessionRef.current) {
      sessionRef.current.latestStrategy = currentStrategy;
    }
  }, [currentStrategy]);

  const createSession = useCallback(
    () => new StreamingSession(currentStrategy),
    [currentStrategy],
  );

  const addStep = useStrategyStore((s) => s.addStep);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const setWdkInfo = useStrategyStore((s) => s.setWdkInfo);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const clearStrategy = useStrategyStore((s) => s.clear);
  const stepsById = useStrategyStore((s) => s.stepsById);
  const addStrategy = useStrategyListStore((s) => s.addStrategy);
  const addExecutedStrategy = useStrategyListStore((s) => s.addExecutedStrategy);

  // Error handling
  const handleError = useCallback(
    (error: unknown, fallback: string) => {
      const isUnauthorized =
        error instanceof APIError
          ? error.status === 401
          : error instanceof Error && /HTTP 401\b/.test(error.message);
      if (isUnauthorized) {
        setAuthToken(null);
        setPlanSessionId(null);
        setMessages([]);
        setSessionArtifacts([]);
        setChatIsStreaming(false);
        setApiError("Session expired. Refresh to start a new plan.");
        return;
      }
      setApiError(toUserMessage(error, fallback));
    },
    [setAuthToken, setPlanSessionId, setChatIsStreaming],
  );

  // Graph loading (execute mode)
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

  const attachThinkingToLastAssistant = useCallback(
    (
      calls: ToolCall[],
      activity?: {
        calls: Record<string, ToolCall[]>;
        status: Record<string, string>;
      },
    ) => {
      if (calls.length === 0 && !activity) return;
      setMessages((prev) => {
        for (let i = prev.length - 1; i >= 0; i -= 1) {
          if (prev[i].role !== "assistant") continue;
          const hasTools = (prev[i].toolCalls?.length || 0) > 0;
          const hasActivity =
            Object.keys(prev[i].subKaniActivity?.calls || {}).length > 0;
          if (hasTools && hasActivity) return prev;
          const next = [...prev];
          next[i] = {
            ...prev[i],
            toolCalls: hasTools || calls.length === 0 ? prev[i].toolCalls : calls,
            subKaniActivity:
              hasActivity || !activity ? prev[i].subKaniActivity : activity,
          };
          return next;
        }
        return prev;
      });
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

  // Plan-mode helpers (executor build, delegation)
  const startExecutorBuild = useCallback(
    (messageText: string) => {
      openAndHydrateDraftStrategy({
        siteId,
        open: () => openStrategy({ siteId }),
        getStrategy,
        nowIso: () => new Date().toISOString(),
        setStrategyId: setStrategyIdGlobal,
        addStrategy,
        clearStrategy,
        setStrategy,
        setStrategyMeta,
        onHydrateSuccess: (full) => {
          if (planSessionId) {
            linkConversation(planSessionId, full.id);
          }
          // Store for the auto-execute effect (fires after mode flips to "execute").
          setPendingAutoExecute({
            strategyId: full.id,
            prompt: messageText,
          });
        },
        onHydrateError: (error) => {
          setApiError(toUserMessage(error, "Failed to load the new strategy."));
        },
      }).catch((error) => {
        setApiError(toUserMessage(error, "Failed to open a new strategy."));
      });
    },
    [
      addStrategy,
      clearStrategy,
      linkConversation,
      planSessionId,
      setStrategy,
      setStrategyIdGlobal,
      setStrategyMeta,
      siteId,
    ],
  );

  const delegationDraft = getDelegationDraft(sessionArtifacts);

  // Plan-mode callbacks for useChatStreaming
  const onPlanSessionId = useCallback(
    (id: string) => setPlanSessionId(id),
    [setPlanSessionId],
  );

  const onPlanningArtifactUpdate = useCallback((artifact: PlanningArtifact) => {
    setSessionArtifacts((prev) => upsertSessionArtifact(prev, artifact));
  }, []);

  const onExecutorBuildRequest = useCallback((message: string) => {
    setPendingExecutorBuildMessage(message);
  }, []);

  const onConversationTitleUpdate = useCallback(
    (_title: string) => {
      bumpPlanListVersion();
    },
    [bumpPlanListVersion],
  );

  const onStreamComplete = useCallback(() => {
    setChatIsStreaming(false);
    setPendingExecutorBuildMessage((msg) => {
      if (msg) {
        window.setTimeout(() => startExecutorBuild(msg), 1000);
      }
      return null;
    });
  }, [setChatIsStreaming, startExecutorBuild]);

  const onStreamError = useCallback(
    (error: Error) => {
      setChatIsStreaming(false);
      handleError(error, "Unable to reach the API.");
      setPendingExecutorBuildMessage(null);
    },
    [setChatIsStreaming, handleError],
  );

  // Build model selection for the current request
  const currentModelSelection = buildModelSelection(
    selectedModelId,
    reasoningEffort,
    modelCatalog,
  );

  // useChatStreaming - one instance, mode-aware
  const streamingArgs = useUnifiedChatStreamingArgs({
    chatMode,
    siteId,
    strategyId,
    planSessionId,
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
    attachThinkingToLastAssistant,
    currentModelSelection,
    referenceStrategyIdProp,
    onPlanSessionId,
    onPlanningArtifactUpdate,
    onExecutorBuildRequest,
    onConversationTitleUpdate,
    setApiError,
    onStreamComplete,
    onStreamError,
    setChatIsStreaming,
    handleError,
  });

  const {
    handleSendMessage: handleSendRaw,
    handleAutoExecute,
    stopStreaming,
    isStreaming,
    setIsStreaming,
    optimizationProgress,
  } = useChatStreaming(streamingArgs);

  // Sync streaming state globally
  useEffect(() => {
    setChatIsStreaming(isStreaming);
  }, [isStreaming, setChatIsStreaming]);

  // Plan-mode: wrap send to bump list version
  const onSend = useCallback(
    async (content: string) => {
      setChatIsStreaming(true);
      setApiError(null);
      if (chatMode === "plan") bumpPlanListVersion();
      await handleSendRaw(content);
      // Consume the reference strategy after it's been sent with the message.
      onConsumeReferenceStrategy?.();
    },
    [
      handleSendRaw,
      setChatIsStreaming,
      chatMode,
      bumpPlanListVersion,
      onConsumeReferenceStrategy,
    ],
  );

  useUnifiedChatDataLoading({
    chatMode,
    planSessionId,
    strategyId,
    isStreaming,
    sessionRef,
    setMessages,
    setSessionArtifacts,
    setApiError,
    setSelectedModelId,
    thinking,
    handleError,
    loadGraph,
  });

  // Auto-execute after plan→execute transition
  useEffect(() => {
    if (!pendingAutoExecute) return;
    if (!strategyId || pendingAutoExecute.strategyId !== strategyId) return;
    if (isStreaming) return;

    const prompt = pendingAutoExecute.prompt.trim();
    setPendingAutoExecute(null);
    if (!prompt) return;

    setChatIsStreaming(true);
    handleAutoExecute(prompt, pendingAutoExecute.strategyId);
  }, [
    strategyId,
    isStreaming,
    pendingAutoExecute,
    handleAutoExecute,
    setChatIsStreaming,
  ]);

  // Hooks for execute-mode features
  useChatPreviewUpdate(
    chatMode === "execute" ? strategyId : null,
    `${messages.length}`,
  );

  useResetOnStrategyChange({
    strategyId: executeStrategyId,
    previousStrategyId,
    isStreaming,
    resetThinking: thinking.reset,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    sessionRef,
  });

  useChatAutoScroll(messagesEndRef, `${messages.length}:${isStreaming ? "s" : "i"}`);

  useConsumePendingAskNode({
    enabled: true,
    pendingAskNode,
    setDraftSelection,
    onConsumeAskNode,
  });

  // Render

  return (
    <div className="flex h-full flex-col bg-white text-[13px]">
      {chatMode === "plan" && delegationDraft && (
        <DelegationDraftViewer
          delegationDraft={delegationDraft}
          onBuildExecutor={startExecutorBuild}
        />
      )}

      {/* Messages */}
      <ChatMessageList
        isCompact={false}
        siteId={siteId}
        displayName={displayName}
        firstName={firstName}
        signedIn={veupathdbSignedIn}
        mode={chatMode}
        isStreaming={isStreaming}
        messages={messages}
        undoSnapshots={chatMode === "execute" ? undoSnapshots : {}}
        onSend={onSend}
        onUndoSnapshot={
          chatMode === "execute"
            ? (snapshot) => {
                setStrategy(snapshot);
                setStrategyMeta({
                  name: snapshot.name,
                  description: snapshot.description ?? undefined,
                  recordType: snapshot.recordType ?? undefined,
                });
              }
            : () => {}
        }
        onApplyPlanningArtifact={
          chatMode === "execute"
            ? async (artifact) => {
                if (!strategyId) return;
                const proposed = artifact.proposedStrategyPlan;
                if (
                  !proposed ||
                  typeof proposed !== "object" ||
                  Array.isArray(proposed)
                )
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
              }
            : undefined
        }
        thinking={thinking}
        optimizationProgress={optimizationProgress}
        onCancelOptimization={stopStreaming}
        messagesEndRef={messagesEndRef}
      />

      {/* Composer area */}
      <div className="border-t border-slate-200 bg-white p-3">
        {apiError && (
          <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {apiError}
          </div>
        )}
        {draftSelection && chatMode === "execute" && (
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
          models={modelCatalog}
          selectedModelId={selectedModelId}
          onModelChange={setSelectedModelId}
          reasoningEffort={reasoningEffort}
          onReasoningChange={setReasoningEffort}
          onInsertStrategy={onInsertStrategy}
          serverDefaultModelId={catalogDefault}
        />
      </div>
    </div>
  );
}
