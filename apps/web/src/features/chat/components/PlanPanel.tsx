"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Citation, Message, PlanningArtifact, ToolCall } from "@pathfinder/shared";
import { Pencil, Save, X } from "lucide-react";
import {
  getPlanSession,
  openStrategy,
  getStrategy,
  updatePlanSession,
} from "@/lib/api/client";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/useStrategyStore";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import { ChatMessageList } from "@/features/chat/components/ChatMessageList";
import { MessageComposer } from "@/features/chat/components/MessageComposer";
import { streamChat } from "@/features/chat/stream";
import type { ChatSSEEvent } from "@/features/chat/sse_events";
import { parseToolArguments } from "@/features/chat/utils/parseToolArguments";

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

  const clearStrategy = useStrategyStore((s) => s.clear);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const addStrategy = useStrategyListStore((s) => s.addStrategy);

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
      .catch(() => {});
  }, [planSessionId, isStreaming, applyThinkingPayload, setChatIsStreaming, reset]);

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
          const finalContent = content || "";

          const idx = streamingAssistantIndexRef.current;
          if (
            idx !== null &&
            idx >= 0 &&
            (!messageId || streamingAssistantMessageIdRef.current === messageId)
          ) {
            setMessages((prev) => {
              if (idx < 0 || idx >= prev.length) return prev;
              const next = [...prev];
              const existing = next[idx];
              if (!existing || existing.role !== "assistant") return prev;
              next[idx] = {
                ...existing,
                content: finalContent || existing.content,
                toolCalls:
                  toolCallsBuffer.length > 0
                    ? [...toolCallsBuffer]
                    : existing.toolCalls,
                citations:
                  citationsBuffer.length > 0
                    ? [...citationsBuffer]
                    : existing.citations,
                planningArtifacts:
                  artifactsBuffer.length > 0
                    ? [...artifactsBuffer]
                    : existing.planningArtifacts,
              };
              return next;
            });
          } else if (finalContent) {
            const assistantMessage: Message = {
              role: "assistant",
              content: finalContent,
              toolCalls: toolCallsBuffer.length > 0 ? [...toolCallsBuffer] : undefined,
              citations: citationsBuffer.length > 0 ? [...citationsBuffer] : undefined,
              planningArtifacts:
                artifactsBuffer.length > 0 ? [...artifactsBuffer] : undefined,
              timestamp: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, assistantMessage]);
          }

          streamingAssistantIndexRef.current = null;
          streamingAssistantMessageIdRef.current = null;
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
          if (!delta) break;
          if (
            streamingAssistantIndexRef.current === null ||
            (messageId && streamingAssistantMessageIdRef.current !== messageId)
          ) {
            const assistantMessage: Message = {
              role: "assistant",
              content: delta,
              timestamp: new Date().toISOString(),
            };
            setMessages((prev) => {
              const next = [...prev, assistantMessage];
              streamingAssistantIndexRef.current = next.length - 1;
              streamingAssistantMessageIdRef.current = messageId || null;
              return next;
            });
            break;
          }
          const idx = streamingAssistantIndexRef.current;
          if (idx === null) break;
          setMessages((prev) => {
            if (idx < 0 || idx >= prev.length) return prev;
            const next = [...prev];
            const existing = next[idx];
            if (!existing || existing.role !== "assistant") return prev;
            next[idx] = { ...existing, content: (existing.content || "") + delta };
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
            setSessionArtifacts((prev) => {
              const next = [...prev];
              const id = planningArtifact?.id;
              if (typeof id === "string" && id) {
                const idx = next.findIndex((a) => a.id === id);
                if (idx >= 0) next[idx] = planningArtifact;
                else next.push(planningArtifact);
                return next;
              }
              next.push(planningArtifact);
              return next;
            });
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
            // Switch to executor mode and create a new strategy. The executor chat will auto-send
            // the message once it mounts; do not prefill the composer (leave input empty).
            setChatMode("execute");
            openStrategy({ siteId })
              .then(async (response) => {
                const nextId = response.strategyId;
                setStrategyId(nextId);
                addStrategy({
                  id: nextId,
                  name: "Draft Strategy",
                  title: "Draft Strategy",
                  siteId,
                  recordType: null,
                  stepCount: 0,
                  resultCount: undefined,
                  wdkStrategyId: undefined,
                  createdAt: new Date().toISOString(),
                  updatedAt: new Date().toISOString(),
                });
                clearStrategy();
                const full = await getStrategy(nextId);
                setStrategy(full);
                setStrategyMeta({
                  name: full.name,
                  recordType: full.recordType ?? undefined,
                  siteId: full.siteId,
                });
                window.dispatchEvent(new Event("pathfinder:open-executor-chat"));
                // Persist a pending send so executor chat can send after it mounts.
                setPendingExecutorSend({ strategyId: nextId, message: messageText });
              })
              .catch(() => {});
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
      addStrategy,
      clearStrategy,
      setAuthToken,
      setChatMode,
      setMessages,
      setPendingExecutorSend,
      setPlanSessionId,
      setStrategy,
      setStrategyId,
      setStrategyMeta,
      siteId,
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
          },
          onError: (error) => {
            setIsStreaming(false);
            setChatIsStreaming(false);
            abortRef.current = null;
            finalizeToolCalls(toolCalls.length > 0 ? [...toolCalls] : []);
            setApiError(error.message || "Unable to reach the API.");
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
    ],
  );

  return (
    <div className="flex h-full flex-col bg-white text-[13px]">
      <div className="border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          {isEditingTitle ? (
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <input
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-[13px] text-slate-900"
                placeholder="Plan title"
                disabled={isStreaming}
              />
              <button
                type="button"
                onClick={async () => {
                  if (!planSessionId) return;
                  const next = draftTitle.trim() || "Plan";
                  await updatePlanSession(planSessionId, { title: next }).catch(
                    () => {},
                  );
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
                <div className="truncate text-sm font-semibold text-slate-900">
                  {planTitle}
                </div>
                <div className="text-[11px] text-slate-500">Planning session</div>
              </div>
              <button
                type="button"
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
      {sessionArtifacts.some((a) => a.id === "delegation_draft") && (
        <div className="border-b border-slate-200 bg-white px-4 py-3">
          {(() => {
            const draft = sessionArtifacts.find((a) => a.id === "delegation_draft");
            const params =
              draft?.parameters &&
              typeof draft.parameters === "object" &&
              !Array.isArray(draft.parameters)
                ? (draft.parameters as Record<string, unknown>)
                : {};
            const goal = params.delegationGoal;
            const plan = params.delegationPlan;
            return (
              <details className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Delegation plan (draft)
                </summary>
                <div className="mt-2 space-y-2 text-[12px] text-slate-700">
                  {typeof goal === "string" && goal.trim() ? (
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                        Goal
                      </div>
                      <div className="mt-1 rounded-md border border-slate-100 bg-slate-50 p-2 text-[12px] text-slate-700">
                        {goal}
                      </div>
                    </div>
                  ) : null}
                  {plan ? (
                    <div>
                      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                        Plan JSON
                      </div>
                      <pre className="mt-1 max-h-64 overflow-auto rounded-md border border-slate-100 bg-slate-50 p-2 text-[11px] text-slate-700">
                        {JSON.stringify(plan, null, 2)}
                      </pre>
                    </div>
                  ) : null}
                  <div className="flex justify-end">
                    <button
                      type="button"
                      className="rounded-md border border-slate-200 bg-slate-900 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-white"
                      onClick={() => {
                        const message = [
                          "Build this strategy using delegation.",
                          "",
                          "You MUST call `delegate_strategy_subtasks(goal, plan)` with the JSON below.",
                          "Use any per-task `context` fields as required parameters/constraints.",
                          "",
                          "Goal:",
                          typeof goal === "string" ? goal : "",
                          "",
                          "Delegation plan (JSON):",
                          "```",
                          JSON.stringify(plan || {}, null, 2),
                          "```",
                        ].join("\n");
                        setChatMode("execute");
                        openStrategy({ siteId })
                          .then(async (response) => {
                            const nextId = response.strategyId;
                            setStrategyId(nextId);
                            addStrategy({
                              id: nextId,
                              name: "Draft Strategy",
                              title: "Draft Strategy",
                              siteId,
                              recordType: null,
                              stepCount: 0,
                              resultCount: undefined,
                              wdkStrategyId: undefined,
                              createdAt: new Date().toISOString(),
                              updatedAt: new Date().toISOString(),
                            });
                            clearStrategy();
                            const full = await getStrategy(nextId);
                            setStrategy(full);
                            setStrategyMeta({
                              name: full.name,
                              recordType: full.recordType ?? undefined,
                              siteId: full.siteId,
                            });
                            window.dispatchEvent(
                              new Event("pathfinder:open-executor-chat"),
                            );
                            setPendingExecutorSend({ strategyId: nextId, message });
                          })
                          .catch(() => {});
                      }}
                    >
                      Build in executor
                    </button>
                  </div>
                </div>
              </details>
            );
          })()}
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
