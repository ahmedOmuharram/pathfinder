"use client";

/**
 * UnifiedChatPanel — single chat view for both planning and execution.
 *
 * Mode is **auto-detected**: if a strategy is attached, the panel uses
 * execute mode; otherwise it uses plan mode. There is no user-facing toggle.
 */

import { useCallback, useEffect, useRef, useState, startTransition } from "react";
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
import {
  buildDelegationExecutorMessage,
  getDelegationDraft,
} from "@/features/chat/utils/delegationDraft";
import { useLatestRef } from "@/shared/hooks/useLatestRef";
import { useChatPreviewUpdate } from "@/features/chat/hooks/useChatPreviewUpdate";
import { useChatAutoScroll } from "@/features/chat/hooks/useChatAutoScroll";
import { useConsumePendingAskNode } from "@/features/chat/hooks/useConsumePendingAskNode";
import { useResetOnStrategyChange } from "@/features/chat/hooks/useResetOnStrategyChange";
import { parseToolArguments } from "@/features/chat/utils/parseToolArguments";
import { parseToolResult } from "@/features/chat/utils/parseToolResult";
import { mergeMessages } from "@/features/chat/utils/mergeMessages";
import { useGraphSnapshot } from "@/features/chat/hooks/useGraphSnapshot";
import type { ModelCatalogEntry } from "@pathfinder/shared";

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
  // -----------------------------------------------------------------------
  // Global state
  // -----------------------------------------------------------------------
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyIdGlobal = useSessionStore((s) => s.setStrategyId);
  const planSessionId = useSessionStore((s) => s.planSessionId);
  const setPlanSessionId = useSessionStore((s) => s.setPlanSessionId);
  const setAuthToken = useSessionStore((s) => s.setAuthToken);
  const setChatIsStreaming = useSessionStore((s) => s.setChatIsStreaming);
  const setPendingExecutorSend = useSessionStore((s) => s.setPendingExecutorSend);
  const pendingExecutorSend = useSessionStore((s) => s.pendingExecutorSend);
  const bumpPlanListVersion = useSessionStore((s) => s.bumpPlanListVersion);
  const setOpenExecutorChat = useSessionStore((s) => s.setOpenExecutorChat);
  const selectedSiteDisplayName = useSessionStore((s) => s.selectedSiteDisplayName);
  const veupathdbSignedIn = useSessionStore((s) => s.veupathdbSignedIn);
  const veupathdbName = useSessionStore((s) => s.veupathdbName);
  const setComposerPrefill = useSessionStore((s) => s.setComposerPrefill);
  const linkConversation = useSessionStore((s) => s.linkConversation);

  const firstName = veupathdbName?.split(" ")[0];
  const displayName = selectedSiteDisplayName || siteId;

  // -----------------------------------------------------------------------
  // Derived mode — the core of the unified conversation model.
  // If a strategy is attached, we're in execute mode; otherwise plan mode.
  // -----------------------------------------------------------------------
  const chatMode: ChatMode = strategyId ? "execute" : "plan";

  // -----------------------------------------------------------------------
  // Settings / model state
  // -----------------------------------------------------------------------
  const modelCatalog = useSettingsStore((s) => s.modelCatalog);
  const setModelCatalog = useSettingsStore((s) => s.setModelCatalog);
  const catalogDefaults = useSettingsStore((s) => s.catalogDefaults);
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
      .then(({ models, defaults }) => setModelCatalog(models, defaults))
      .catch((err) => console.warn("[UnifiedChat] Failed to load models:", err));
  }, [setModelCatalog]);

  // -----------------------------------------------------------------------
  // Local state
  // -----------------------------------------------------------------------
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
  const lastPlanSessionIdRef = useRef<string | null>(null);
  const pendingExecutorBuildMessageRef = useRef<string | null>(null);
  const pendingUndoSnapshotRef = useRef<StrategyWithMeta | null>(null);
  const appliedSnapshotRef = useRef(false);
  const isStreamingRef = useRef(false);
  const previousStrategyIdRef = useRef<string | null>(null);

  // -----------------------------------------------------------------------
  // Strategy store
  // -----------------------------------------------------------------------
  const currentStrategy = useStrategyStore((s) => s.strategy);
  const strategyRef = useLatestRef(currentStrategy);
  const addStep = useStrategyStore((s) => s.addStep);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const setWdkInfo = useStrategyStore((s) => s.setWdkInfo);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const clearStrategy = useStrategyStore((s) => s.clear);
  const stepsById = useStrategyStore((s) => s.stepsById);
  const addStrategy = useStrategyListStore((s) => s.addStrategy);
  const addExecutedStrategy = useStrategyListStore((s) => s.addExecutedStrategy);

  // -----------------------------------------------------------------------
  // Error handling
  // -----------------------------------------------------------------------
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

  // -----------------------------------------------------------------------
  // Graph loading (execute mode)
  // -----------------------------------------------------------------------
  const loadGraph = useCallback(
    (graphId: string) => {
      if (!graphId) return;
      getStrategy(graphId)
        .then((full) => {
          if (appliedSnapshotRef.current) return;
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
    strategyRef,
    pendingUndoSnapshotRef,
    appliedSnapshotRef,
    setStrategy,
    setStrategyMeta,
  });

  // -----------------------------------------------------------------------
  // Plan-mode helpers (executor build, delegation)
  // -----------------------------------------------------------------------
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
          // Link this plan session to the newly created strategy
          if (planSessionId) {
            linkConversation(planSessionId, full.id);
          }
          setOpenExecutorChat(true);
          setPendingExecutorSend({
            strategyId: full.id,
            message: messageText,
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
      setPendingExecutorSend,
      setOpenExecutorChat,
      setStrategy,
      setStrategyIdGlobal,
      setStrategyMeta,
      siteId,
    ],
  );

  const delegationDraft = getDelegationDraft(sessionArtifacts);

  // -----------------------------------------------------------------------
  // Plan-mode callbacks for useChatStreaming
  // -----------------------------------------------------------------------
  const onPlanSessionId = useCallback(
    (id: string) => setPlanSessionId(id),
    [setPlanSessionId],
  );

  const onPlanningArtifactUpdate = useCallback((artifact: PlanningArtifact) => {
    setSessionArtifacts((prev) => upsertSessionArtifact(prev, artifact));
  }, []);

  const onExecutorBuildRequest = useCallback((message: string) => {
    pendingExecutorBuildMessageRef.current = message;
  }, []);

  const onPlanTitleUpdate = useCallback(
    (_title: string) => {
      bumpPlanListVersion();
    },
    [bumpPlanListVersion],
  );

  const onStreamComplete = useCallback(() => {
    setChatIsStreaming(false);
    const msg = pendingExecutorBuildMessageRef.current;
    if (msg) {
      pendingExecutorBuildMessageRef.current = null;
      window.setTimeout(() => startExecutorBuild(msg), 1000);
    }
  }, [setChatIsStreaming, startExecutorBuild]);

  const onStreamError = useCallback(
    (error: Error) => {
      setChatIsStreaming(false);
      handleError(error, "Unable to reach the API.");
      pendingExecutorBuildMessageRef.current = null;
    },
    [setChatIsStreaming, handleError],
  );

  // -----------------------------------------------------------------------
  // Plan-mode no-op stubs
  // -----------------------------------------------------------------------
  const noopSetDraftSelection = useCallback(() => {}, []);
  const noopSetUndoSnapshots = useCallback(
    (() => {}) as React.Dispatch<
      React.SetStateAction<Record<number, StrategyWithMeta>>
    >,
    [],
  );
  const noopLoadGraph = useCallback(() => {}, []);
  const noopAddStep = useCallback(() => {}, []);
  const noopParseToolArguments = useCallback(
    (args: unknown) =>
      typeof args === "object" && args ? (args as Record<string, unknown>) : {},
    [],
  );
  const noopParseToolResult = useCallback(() => null, []);
  const noopApplyGraphSnapshot = useCallback(() => {}, []);
  const noopGetStrategy = useCallback(() => Promise.resolve(null as never), []);
  const noopAttachThinking = useCallback(() => {}, []);
  const noopAddExecutedStrategy = useCallback(() => {}, []);
  const noopSetWdkInfo = useCallback(() => {}, []);

  // -----------------------------------------------------------------------
  // Build model selection for the current request
  // -----------------------------------------------------------------------
  const currentModelSelection = buildModelSelection(
    selectedModelId,
    reasoningEffort,
    modelCatalog,
  );

  // -----------------------------------------------------------------------
  // useChatStreaming - one instance, mode-aware
  // -----------------------------------------------------------------------
  const streamingArgs =
    chatMode === "plan"
      ? {
          siteId,
          strategyId: null as string | null,
          planSessionId,
          draftSelection: null,
          setDraftSelection: noopSetDraftSelection,
          thinking,
          setMessages,
          setUndoSnapshots: noopSetUndoSnapshots,
          pendingUndoSnapshotRef,
          appliedSnapshotRef,
          loadGraph: noopLoadGraph,
          addStrategy: noopAddExecutedStrategy,
          addExecutedStrategy: noopAddExecutedStrategy,
          setStrategyId: noopLoadGraph,
          setWdkInfo: noopSetWdkInfo,
          setStrategy: noopLoadGraph as (s: StrategyWithMeta | null) => void,
          setStrategyMeta: noopLoadGraph as (m: Record<string, unknown>) => void,
          clearStrategy: noopLoadGraph,
          addStep: noopAddStep,
          parseToolArguments: noopParseToolArguments,
          parseToolResult: noopParseToolResult,
          applyGraphSnapshot: noopApplyGraphSnapshot,
          getStrategy: noopGetStrategy,
          strategyRef: {
            current: null,
          } as React.MutableRefObject<StrategyWithMeta | null>,
          currentStrategy: null,
          attachThinkingToLastAssistant: noopAttachThinking,
          mode: "plan" as ChatMode,
          modelSelection: currentModelSelection,
          referenceStrategyId: referenceStrategyIdProp,
          onPlanSessionId,
          onPlanningArtifactUpdate,
          onExecutorBuildRequest,
          onPlanTitleUpdate,
          onApiError: (msg: string) => setApiError(msg),
          onStreamComplete,
          onStreamError,
        }
      : {
          siteId,
          strategyId,
          draftSelection,
          setDraftSelection,
          thinking,
          setMessages,
          setUndoSnapshots,
          pendingUndoSnapshotRef,
          appliedSnapshotRef,
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
          strategyRef,
          currentStrategy,
          attachThinkingToLastAssistant,
          mode: "execute" as ChatMode,
          modelSelection: currentModelSelection,
          onStreamComplete: () => setChatIsStreaming(false),
          onStreamError: (error: Error) => {
            setChatIsStreaming(false);
            handleError(error, "Unable to reach the API.");
          },
        };

  const {
    handleSendMessage: handleSendRaw,
    stopStreaming,
    isStreaming,
    setIsStreaming,
  } = useChatStreaming(streamingArgs);

  // -----------------------------------------------------------------------
  // Sync streaming state globally
  // -----------------------------------------------------------------------
  useEffect(() => {
    setChatIsStreaming(isStreaming);
  }, [isStreaming, setChatIsStreaming]);
  useEffect(() => {
    isStreamingRef.current = isStreaming;
  }, [isStreaming]);

  // -----------------------------------------------------------------------
  // Plan-mode: wrap send to bump list version
  // -----------------------------------------------------------------------
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

  // -----------------------------------------------------------------------
  // Load plan session messages when plan session changes
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (chatMode !== "plan") return;
    if (!planSessionId) {
      if (isStreaming) return;
      startTransition(() => setMessages([]));
      return;
    }
    if (isStreaming) return;
    if (lastPlanSessionIdRef.current !== planSessionId) {
      lastPlanSessionIdRef.current = planSessionId;
      startTransition(() => {
        setMessages([]);
        setSessionArtifacts([]);
        setApiError(null);
      });
      thinking.reset();
    }
    getPlanSession(planSessionId)
      .then((ps) => {
        setMessages(ps.messages || []);
        setSessionArtifacts(ps.planningArtifacts || []);
        if (ps.thinking) {
          if (thinking.applyThinkingPayload(ps.thinking)) {
            setIsStreaming(true);
            setChatIsStreaming(true);
          }
        }
      })
      .catch((error) => {
        handleError(error, "Failed to load plan.");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatMode, planSessionId, isStreaming]);

  // -----------------------------------------------------------------------
  // Load strategy messages when strategy changes (execute mode)
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (chatMode !== "execute") return;
    if (!strategyId) {
      if (isStreaming) return;
      startTransition(() => setMessages([]));
      return;
    }
    if (isStreaming) return;
    getStrategy(strategyId)
      .then((strategy) => {
        setMessages((prev) => mergeMessages(prev, strategy.messages || []));
        if (!isStreaming && strategy.thinking) {
          if (thinking.applyThinkingPayload(strategy.thinking)) {
            setIsStreaming(true);
          }
        }
        if (strategy.id && !appliedSnapshotRef.current) {
          loadGraph(strategy.id);
        }
      })
      .catch((err) => {
        console.warn("[UnifiedChat] Failed to fetch strategy messages:", err);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatMode, strategyId, isStreaming]);

  // -----------------------------------------------------------------------
  // Send pending executor message (from plan -> executor build flow)
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!pendingExecutorSend) return;
    if (!strategyId) return;
    if (pendingExecutorSend.strategyId !== strategyId) return;
    if (isStreamingRef.current) return;
    const msg = (pendingExecutorSend.message || "").trim();
    if (!msg) {
      setPendingExecutorSend(null);
      return;
    }
    handleSendRaw(msg);
    setComposerPrefill({ mode: "execute", message: "" });
    setPendingExecutorSend(null);
  }, [
    pendingExecutorSend,
    strategyId,
    handleSendRaw,
    setPendingExecutorSend,
    setComposerPrefill,
  ]);

  // -----------------------------------------------------------------------
  // Hooks for execute-mode features
  // -----------------------------------------------------------------------
  useChatPreviewUpdate(
    chatMode === "execute" ? strategyId : null,
    `${messages.length}`,
  );

  useResetOnStrategyChange({
    strategyId: chatMode === "execute" ? strategyId : null,
    isStreamingRef,
    previousStrategyIdRef,
    resetThinking: thinking.reset,
    setIsStreaming,
    setMessages,
    setUndoSnapshots,
    pendingUndoSnapshotRef,
  });

  useChatAutoScroll(messagesEndRef, `${messages.length}:${isStreaming ? "s" : "i"}`);

  useConsumePendingAskNode({
    enabled: true,
    pendingAskNode,
    setDraftSelection,
    onConsumeAskNode,
  });

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div className="flex h-full flex-col bg-white text-[13px]">
      {/* Delegation draft viewer (plan mode) */}
      {chatMode === "plan" && delegationDraft && (
        <div className="border-b border-slate-200 bg-white px-4 py-3">
          <details
            className="rounded-lg border border-slate-200 bg-white px-3 py-2"
            data-testid="delegation-draft-details"
          >
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-slate-500">
              Delegation plan (draft)
            </summary>
            <div className="mt-2 space-y-2 text-[12px] text-slate-700">
              {typeof delegationDraft.goal === "string" &&
              delegationDraft.goal.trim() ? (
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Goal
                  </div>
                  <div className="mt-1 rounded-md border border-slate-100 bg-slate-50 p-2 text-[12px] text-slate-700">
                    {delegationDraft.goal}
                  </div>
                </div>
              ) : null}
              {delegationDraft.plan ? (
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    Plan JSON
                  </div>
                  <pre className="mt-1 max-h-64 overflow-auto rounded-md border border-slate-100 bg-slate-50 p-2 text-[11px] text-slate-700">
                    {JSON.stringify(delegationDraft.plan, null, 2)}
                  </pre>
                </div>
              ) : null}
              <div className="flex justify-end">
                <button
                  type="button"
                  data-testid="delegation-build-executor"
                  className="rounded-md border border-slate-200 bg-slate-900 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-white"
                  onClick={() =>
                    startExecutorBuild(buildDelegationExecutorMessage(delegationDraft))
                  }
                >
                  Build in executor
                </button>
              </div>
            </div>
          </details>
        </div>
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
          onInsertStrategy={chatMode === "plan" ? onInsertStrategy : undefined}
          serverDefaultModelId={
            catalogDefaults
              ? chatMode === "plan"
                ? catalogDefaults.plan
                : catalogDefaults.execute
              : null
          }
        />
      </div>
    </div>
  );
}
