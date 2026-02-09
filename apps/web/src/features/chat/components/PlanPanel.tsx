"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Citation, Message, PlanningArtifact, ToolCall } from "@pathfinder/shared";
import { Pencil, Save, X } from "lucide-react";
import {
  APIError,
  getPlanSession,
  openStrategy,
  getStrategy,
  updatePlanSession,
} from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/useStrategyStore";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import { MessageComposer } from "@/features/chat/components/MessageComposer";
import { streamChat } from "@/features/chat/stream";
import type { ChatSSEEvent } from "@/features/chat/sse_events";
import { parseToolArguments } from "@/features/chat/utils/parseToolArguments";
import {
  applyAssistantDelta,
  finalizeAssistantMessage,
  upsertSessionArtifact,
} from "@/features/chat/utils/planStreamState";
import { openAndHydrateDraftStrategy } from "@/features/strategy/services/openAndHydrateDraftStrategy";
import {
  buildDelegationExecutorMessage,
  getDelegationDraft,
} from "@/features/chat/utils/delegationDraft";

export function PlanPanel(props: { siteId: string }) {
  const { siteId } = props;
  const planSessionId = useSessionStore((s) => s.planSessionId);
  const setPlanSessionId = useSessionStore((s) => s.setPlanSessionId);
  const setAuthToken = useSessionStore((s) => s.setAuthToken);
  const setChatIsStreaming = useSessionStore((s) => s.setChatIsStreaming);
  const setChatMode = useSessionStore((s) => s.setChatMode);
  const setStrategyId = useSessionStore((s) => s.setStrategyId);
  const setPendingExecutorSend = useSessionStore((s) => s.setPendingExecutorSend);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionArtifacts, setSessionArtifacts] = useState<PlanningArtifact[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [planTitle, setPlanTitle] = useState("Plan");
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [draftTitle, setDraftTitle] = useState("Plan");
  const {
    activeToolCalls,
    lastToolCalls,
    subKaniCalls,
    subKaniStatus,
    reasoning,
    reset,
    applyThinkingPayload,
    updateActiveFromBuffer,
    finalizeToolCalls,
    updateReasoning,
  } = useThinkingState();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const streamingAssistantIndexRef = useRef<number | null>(null);
  const streamingAssistantMessageIdRef = useRef<string | null>(null);
  const lastPlanSessionIdRef = useRef<string | null>(null);
  const pendingExecutorBuildMessageRef = useRef<string | null>(null);

  const clearStrategy = useStrategyStore((s) => s.clear);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const addStrategy = useStrategyListStore((s) => s.addStrategy);

  const startExecutorBuild = useCallback(
    (messageText: string) => {
      // Switch to executor mode and create a new strategy. The executor chat will auto-send
      // the message once it mounts; do not prefill the composer (leave input empty).
      setChatMode("execute");
      openAndHydrateDraftStrategy({
        siteId,
        open: () => openStrategy({ siteId }),
        getStrategy,
        nowIso: () => new Date().toISOString(),
        setStrategyId,
        addStrategy,
        clearStrategy,
        setStrategy,
        setStrategyMeta,
        onHydrateSuccess: (full) => {
          window.dispatchEvent(new Event("pathfinder:open-executor-chat"));
          setPendingExecutorSend({ strategyId: full.id, message: messageText });
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
      setApiError,
      setChatMode,
      setPendingExecutorSend,
      setStrategy,
      setStrategyId,
      setStrategyMeta,
      siteId,
    ],
  );

  const delegationDraft = getDelegationDraft(sessionArtifacts);

  const handlePlanError = useCallback(
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
        setIsStreaming(false);
        setChatIsStreaming(false);
        setApiError("Session expired. Refresh to start a new plan.");
        return;
      }
      setApiError(toUserMessage(error, fallback));
    },
    [
      setAuthToken,
      setPlanSessionId,
      setMessages,
      setSessionArtifacts,
      setChatIsStreaming,
    ],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  useEffect(() => {
    if (!planSessionId) {
      setMessages([]);
      return;
    }
    if (isStreaming) return;
    // When switching plan sessions, reset local state immediately so the panel is empty.
    if (lastPlanSessionIdRef.current !== planSessionId) {
      lastPlanSessionIdRef.current = planSessionId;
      setMessages([]);
      setSessionArtifacts([]);
      setApiError(null);
      reset();
      streamingAssistantIndexRef.current = null;
      streamingAssistantMessageIdRef.current = null;
      setIsEditingTitle(false);
    }
    getPlanSession(planSessionId)
      .then((ps) => {
        setPlanTitle(ps.title || "Plan");
        setDraftTitle(ps.title || "Plan");
        setMessages(ps.messages || []);
        setSessionArtifacts(ps.planningArtifacts || []);
        if (ps.thinking) {
          if (applyThinkingPayload(ps.thinking)) {
            setIsStreaming(true);
            setChatIsStreaming(true);
          }
        }
      })
      .catch((error) => {
        handlePlanError(error, "Failed to load plan.");
      });
  }, [
    planSessionId,
    isStreaming,
    applyThinkingPayload,
    setChatIsStreaming,
    reset,
    handlePlanError,
  ]);

  const handlePlanEvent = useCallback(
    (
      event: ChatSSEEvent,
      toolCallsBuffer: ToolCall[],
      citationsBuffer: Citation[],
      artifactsBuffer: PlanningArtifact[],
    ) => {
      switch (event.type) {
        case "message_start": {
          if (event.data.planSessionId) setPlanSessionId(event.data.planSessionId);
          if (event.data.authToken) setAuthToken(event.data.authToken);
          break;
        }
        case "assistant_message": {
          const { messageId, content } = event.data as {
            messageId?: string;
            content?: string;
          };
          setMessages((prev) => {
            const { messages: next, streaming } = finalizeAssistantMessage({
              messages: prev,
              streaming: {
                index: streamingAssistantIndexRef.current,
                messageId: streamingAssistantMessageIdRef.current,
              },
              event: { messageId, content },
              toolCallsBuffer,
              citationsBuffer,
              artifactsBuffer,
              nowIso: () => new Date().toISOString(),
            });
            streamingAssistantIndexRef.current = streaming.index;
            streamingAssistantMessageIdRef.current = streaming.messageId;
            return next;
          });
          toolCallsBuffer.length = 0;
          citationsBuffer.length = 0;
          artifactsBuffer.length = 0;
          break;
        }
        case "assistant_delta": {
          const { messageId, delta } = event.data as {
            messageId?: string;
            delta?: string;
          };
          setMessages((prev) => {
            const { messages: next, streaming } = applyAssistantDelta({
              messages: prev,
              streaming: {
                index: streamingAssistantIndexRef.current,
                messageId: streamingAssistantMessageIdRef.current,
              },
              event: { messageId, delta },
              nowIso: () => new Date().toISOString(),
            });
            streamingAssistantIndexRef.current = streaming.index;
            streamingAssistantMessageIdRef.current = streaming.messageId;
            return next;
          });
          break;
        }
        case "tool_call_start": {
          const { id, name, arguments: args } = event.data;
          toolCallsBuffer.push({ id, name, arguments: parseToolArguments(args) });
          updateActiveFromBuffer([...toolCallsBuffer]);
          break;
        }
        case "tool_call_end": {
          const { id, result } = event.data;
          const tc = toolCallsBuffer.find((t) => t.id === id);
          if (tc) tc.result = result;
          updateActiveFromBuffer([...toolCallsBuffer]);
          break;
        }
        case "citations": {
          const citations = event.data.citations;
          if (Array.isArray(citations)) {
            for (const c of citations) {
              if (c && typeof c === "object" && !Array.isArray(c)) {
                citationsBuffer.push(c as Citation);
              }
            }
          }
          break;
        }
        case "planning_artifact": {
          const artifact = event.data.planningArtifact;
          if (artifact && typeof artifact === "object" && !Array.isArray(artifact)) {
            const planningArtifact = artifact as PlanningArtifact;
            artifactsBuffer.push(planningArtifact);
            setSessionArtifacts((prev) =>
              upsertSessionArtifact(prev, planningArtifact),
            );
          }
          break;
        }
        case "executor_build_request": {
          const payload = event.data.executorBuildRequest;
          const message =
            payload && typeof payload === "object" && !Array.isArray(payload)
              ? (payload as Record<string, unknown>).message
              : null;
          const messageText = typeof message === "string" ? message : null;
          if (messageText) {
            // Defer the UI transition until after the plan stream completes so the user
            // can see the plan response (and Playwright can assert on it reliably).
            pendingExecutorBuildMessageRef.current = messageText;
          }
          break;
        }
        case "reasoning": {
          if (typeof event.data.reasoning === "string")
            updateReasoning(event.data.reasoning);
          break;
        }
        case "plan_update": {
          if (typeof event.data.title === "string" && event.data.title.trim()) {
            setPlanTitle(event.data.title.trim());
            setDraftTitle(event.data.title.trim());
            window.dispatchEvent(new Event("plans:update"));
          }
          break;
        }
        case "error": {
          if (typeof event.data.error === "string" && event.data.error.trim()) {
            setApiError(event.data.error.trim());
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: `Error: ${event.data.error.trim()}`,
                timestamp: new Date().toISOString(),
              },
            ]);
          } else {
            setApiError("An unknown error occurred while streaming.");
          }
          break;
        }
        default:
          break;
      }
    },
    [
      setPlanSessionId,
      setAuthToken,
      setMessages,
      setSessionArtifacts,
      setPlanTitle,
      setDraftTitle,
      setApiError,
      updateActiveFromBuffer,
      updateReasoning,
    ],
  );

  const onSend = useCallback(
    async (content: string) => {
      const userMessage: Message = {
        role: "user",
        content,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsStreaming(true);
      setChatIsStreaming(true);
      setApiError(null);
      reset();
      streamingAssistantIndexRef.current = null;
      streamingAssistantMessageIdRef.current = null;
      // Ensure the newly-started plan appears in the sidebar once it becomes non-empty.
      window.dispatchEvent(new Event("plans:update"));

      const controller = new AbortController();
      abortRef.current = controller;

      const toolCalls: ToolCall[] = [];
      const citationsBuffer: Citation[] = [];
      const artifactsBuffer: PlanningArtifact[] = [];
      await streamChat(
        content,
        siteId,
        {
          onMessage: (event) =>
            handlePlanEvent(event, toolCalls, citationsBuffer, artifactsBuffer),
          onComplete: () => {
            setIsStreaming(false);
            setChatIsStreaming(false);
            abortRef.current = null;
            finalizeToolCalls(toolCalls.length > 0 ? [...toolCalls] : []);
            const msg = pendingExecutorBuildMessageRef.current;
            if (msg) {
              pendingExecutorBuildMessageRef.current = null;
              // Small delay to ensure plan transcript renders before switching modes.
              window.setTimeout(() => startExecutorBuild(msg), 1000);
            }
          },
          onError: (error) => {
            setIsStreaming(false);
            setChatIsStreaming(false);
            abortRef.current = null;
            finalizeToolCalls(toolCalls.length > 0 ? [...toolCalls] : []);
            handlePlanError(error, "Unable to reach the API.");
            pendingExecutorBuildMessageRef.current = null;
          },
        },
        { planSessionId: planSessionId ?? undefined },
        "plan",
        controller.signal,
      );
    },
    [
      handlePlanEvent,
      planSessionId,
      siteId,
      reset,
      finalizeToolCalls,
      setChatIsStreaming,
      handlePlanError,
      startExecutorBuild,
    ],
  );

  return (
    <div className="flex h-full flex-col bg-white text-[13px]">
      <div className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          {isEditingTitle ? (
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <input
                data-testid="plan-title-input"
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-[13px] text-slate-900"
                placeholder="Plan title"
                disabled={isStreaming}
              />
              <button
                type="button"
                data-testid="plan-title-save"
                onClick={async () => {
                  if (!planSessionId) return;
                  const next = draftTitle.trim() || "Plan";
                  try {
                    await updatePlanSession(planSessionId, { title: next });
                  } catch (error) {
                    handlePlanError(error, "Failed to update plan title.");
                    return;
                  }
                  setPlanTitle(next);
                  setDraftTitle(next);
                  setIsEditingTitle(false);
                  window.dispatchEvent(new Event("plans:update"));
                }}
                disabled={isStreaming}
                className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-2 text-[12px] text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                title="Save"
                aria-label="Save"
              >
                <Save className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                data-testid="plan-title-cancel"
                onClick={() => {
                  setDraftTitle(planTitle);
                  setIsEditingTitle(false);
                }}
                disabled={isStreaming}
                className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-2 text-[12px] text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                title="Cancel"
                aria-label="Cancel"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          ) : (
            <>
              <div className="min-w-0 flex-1">
                <div
                  data-testid="plan-title"
                  className="truncate text-sm font-semibold text-slate-900"
                >
                  {planTitle}
                </div>
                <div className="text-[11px] text-slate-500">Planning session</div>
              </div>
              <button
                type="button"
                data-testid="plan-title-edit"
                onClick={() => setIsEditingTitle(true)}
                disabled={isStreaming}
                className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-2 text-[12px] text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                title="Edit title"
                aria-label="Edit title"
              >
                <Pencil className="h-4 w-4" aria-hidden="true" />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Delegation plan draft viewer (if present) */}
      {delegationDraft && (
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
      <ChatMessageList
        isCompact={false}
        siteId={siteId}
        displayName={siteId}
        signedIn={false}
        mode="plan"
        isStreaming={isStreaming}
        messages={messages}
        undoSnapshots={{}}
        onSend={onSend}
        onUndoSnapshot={() => {}}
        thinking={{
          activeToolCalls,
          lastToolCalls,
          subKaniCalls,
          subKaniStatus,
          reasoning,
        }}
        messagesEndRef={messagesEndRef}
      />

      <div className="border-t border-slate-200 bg-white p-3">
        {apiError && (
          <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {apiError}
          </div>
        )}
        <MessageComposer
          onSend={onSend}
          disabled={isStreaming}
          isStreaming={isStreaming}
          onStop={stopStreaming}
          mode="plan"
        />
      </div>
    </div>
  );
}
