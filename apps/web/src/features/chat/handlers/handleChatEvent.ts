import type { Dispatch, SetStateAction } from "react";
import type { Message, ToolCall, Citation, PlanningArtifact } from "@pathfinder/shared";
import type { ChatSSEEvent } from "@/features/chat/sse_events";
import type { StrategyStep, StrategyWithMeta } from "@/types/strategy";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { MutableRef } from "@/shared/types/refs";

type Thinking = ReturnType<typeof useThinkingState>;

export type ChatEventContext = {
  siteId: string;
  strategyIdAtStart: string | null;
  toolCallsBuffer: ToolCall[];
  citationsBuffer: Citation[];
  planningArtifactsBuffer: PlanningArtifact[];
  thinking: Thinking;

  // Strategy/session actions
  setStrategyId: (id: string | null) => void;
  setAuthToken: (token: string | null) => void;
  addStrategy: (s: {
    id: string;
    name: string;
    title: string;
    siteId: string;
    recordType: string | null;
    stepCount: number;
    resultCount?: number;
    wdkStrategyId?: number;
    createdAt: string;
    updatedAt: string;
  }) => void;
  addExecutedStrategy: (s: StrategyWithMeta) => void;
  setWdkInfo: (
    wdkStrategyId: number,
    wdkUrl?: string | null,
    name?: string | null,
    description?: string | null,
  ) => void;
  setStrategy: (s: StrategyWithMeta | null) => void;
  setStrategyMeta: (u: Partial<StrategyWithMeta>) => void;
  clearStrategy: () => void;
  addStep: (s: StrategyStep) => void;
  loadGraph: (graphId: string) => void;

  // Refs/state for undo snapshots
  pendingUndoSnapshotRef: MutableRef<StrategyWithMeta | null>;
  appliedSnapshotRef: MutableRef<boolean>;
  strategyRef: MutableRef<StrategyWithMeta | null>;
  currentStrategy: StrategyWithMeta | null;

  // UI state setters
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setUndoSnapshots: Dispatch<SetStateAction<Record<number, StrategyWithMeta>>>;

  // Helpers
  parseToolArguments: (args: unknown) => Record<string, unknown>;
  parseToolResult: (
    result?: string | null,
  ) => { graphSnapshot?: Record<string, unknown> } | null;
  applyGraphSnapshot: (graphSnapshot: Record<string, unknown>) => void;
  getStrategy: (id: string) => Promise<StrategyWithMeta>;
  streamingAssistantIndexRef: MutableRef<number | null>;
  streamingAssistantMessageIdRef: MutableRef<string | null>;
};

export function handleChatEvent(ctx: ChatEventContext, event: ChatSSEEvent) {
  const {
    siteId,
    strategyIdAtStart,
    toolCallsBuffer,
    citationsBuffer,
    planningArtifactsBuffer,
    thinking,
    setStrategyId,
    setAuthToken,
    addStrategy,
    addExecutedStrategy,
    setWdkInfo,
    setStrategy,
    setStrategyMeta,
    clearStrategy,
    addStep,
    loadGraph,
    pendingUndoSnapshotRef,
    appliedSnapshotRef,
    strategyRef,
    currentStrategy,
    setMessages,
    setUndoSnapshots,
    parseToolArguments,
    parseToolResult,
    applyGraphSnapshot,
    getStrategy,
    streamingAssistantIndexRef,
    streamingAssistantMessageIdRef,
  } = ctx;

  switch (event.type) {
    case "message_start": {
      const { strategyId, authToken, strategy } = event.data as {
        strategyId?: string;
        strategy?: StrategyWithMeta;
        authToken?: string;
      };
      if (strategyId) {
        setStrategyId(strategyId);
        addStrategy({
          id: strategyId,
          name: strategy?.name || "Draft Strategy",
          title: strategy?.title || strategy?.name || "Draft Strategy",
          siteId,
          recordType: strategy?.recordType ?? null,
          stepCount: strategy?.steps?.length ?? 0,
          resultCount: undefined,
          wdkStrategyId: strategy?.wdkStrategyId,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        });
        loadGraph(strategyId);
      }
      if (authToken) setAuthToken(authToken);
      if (strategy) {
        setStrategy(strategy);
        setStrategyMeta({
          name: strategy.name,
          recordType: strategy.recordType ?? undefined,
          siteId: strategy.siteId,
        });
      }
      break;
    }
    case "assistant_delta": {
      const { messageId, delta } = event.data as { messageId?: string; delta?: string };
      if (!delta) break;
      // If this is a new streaming assistant message, append it and remember its index.
      if (
        streamingAssistantIndexRef.current === null ||
        (messageId && streamingAssistantMessageIdRef.current !== messageId)
      ) {
        // Mark refs synchronously so that subsequent events processed within the
        // same synchronous batch (multiple SSE events arriving in one chunk) know
        // a streaming message has been started and don't create duplicate messages.
        // -1 is a sentinel meaning "created but index not yet resolved by React".
        streamingAssistantIndexRef.current = -1;
        streamingAssistantMessageIdRef.current = messageId || null;

        const assistantMessage: Message = {
          role: "assistant",
          content: delta,
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => {
          const next = [...prev, assistantMessage];
          streamingAssistantIndexRef.current = next.length - 1;
          return next;
        });
        break;
      }

      // Append to the existing streaming message.
      // Read the ref inside the updater so the resolved index (set by the
      // preceding "create" updater) is visible even when events are batched.
      setMessages((prev) => {
        const idx = streamingAssistantIndexRef.current;
        if (idx === null || idx < 0 || idx >= prev.length) return prev;
        const next = [...prev];
        const existing = next[idx];
        if (!existing || existing.role !== "assistant") return prev;
        next[idx] = { ...existing, content: (existing.content || "") + delta };
        return next;
      });
      break;
    }
    case "assistant_message": {
      const { messageId, content } = event.data as {
        messageId?: string;
        content?: string;
      };
      const finalContent = content || "";
      const subKaniActivity = thinking.snapshotSubKaniActivity();

      // Snapshot buffer contents now. The buffers are cleared synchronously
      // below, but the updater may not execute until later when React flushes
      // batched state updates (e.g. when multiple SSE events arrive in one chunk).
      const finalToolCalls =
        toolCallsBuffer.length > 0 ? [...toolCallsBuffer] : undefined;
      const finalCitations =
        citationsBuffer.length > 0 ? [...citationsBuffer] : undefined;
      const finalArtifacts =
        planningArtifactsBuffer.length > 0 ? [...planningArtifactsBuffer] : undefined;

      if (
        streamingAssistantIndexRef.current !== null &&
        (!messageId || streamingAssistantMessageIdRef.current === messageId)
      ) {
        // Finalize the in-progress assistant message.
        // Read the ref inside the updater so the resolved index (set by the
        // preceding "create" updater) is visible even when events are batched.
        setMessages((prev) => {
          const idx = streamingAssistantIndexRef.current;
          if (idx === null || idx < 0 || idx >= prev.length) return prev;
          const next = [...prev];
          const existing = next[idx];
          if (!existing || existing.role !== "assistant") return prev;
          next[idx] = {
            ...existing,
            content: finalContent || existing.content,
            toolCalls: finalToolCalls ?? existing.toolCalls,
            subKaniActivity,
            citations: finalCitations ?? existing.citations,
            planningArtifacts: finalArtifacts ?? existing.planningArtifacts,
          };
          // Reset streaming refs atomically with the state update so they
          // are correct when React flushes (avoids stale index after batch).
          streamingAssistantIndexRef.current = null;
          streamingAssistantMessageIdRef.current = null;
          return next;
        });
      } else if (finalContent) {
        // No streaming message active; append as before.
        const assistantMessage: Message = {
          role: "assistant",
          content: finalContent,
          toolCalls: finalToolCalls,
          subKaniActivity,
          citations: finalCitations,
          planningArtifacts: finalArtifacts,
          timestamp: new Date().toISOString(),
        };
        const snapshot = pendingUndoSnapshotRef.current;
        setMessages((prev) => {
          const next = [...prev, assistantMessage];
          if (snapshot) {
            setUndoSnapshots((prevSnapshots) => ({
              ...prevSnapshots,
              [next.length - 1]: snapshot,
            }));
          }
          return next;
        });
      }

      // Reset per-message buffers and streaming pointers.
      pendingUndoSnapshotRef.current = null;
      streamingAssistantIndexRef.current = null;
      streamingAssistantMessageIdRef.current = null;
      toolCallsBuffer.length = 0;
      citationsBuffer.length = 0;
      planningArtifactsBuffer.length = 0;
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
        planningArtifactsBuffer.push(artifact as PlanningArtifact);
      }
      break;
    }
    case "reasoning": {
      const reasoning = (event.data as { reasoning?: string })?.reasoning;
      if (typeof reasoning === "string") {
        thinking.updateReasoning(reasoning);
      }
      break;
    }
    case "tool_call_start": {
      const {
        id,
        name,
        arguments: args,
      } = event.data as {
        id: string;
        name: string;
        arguments?: string;
      };
      const newToolCall: ToolCall = { id, name, arguments: parseToolArguments(args) };
      toolCallsBuffer.push(newToolCall);
      thinking.updateActiveFromBuffer([...toolCallsBuffer]);
      break;
    }
    case "tool_call_end": {
      const { id, result } = event.data as { id: string; result: string };
      const tc = toolCallsBuffer.find((t) => t.id === id);
      if (tc) {
        tc.result = result;
        thinking.updateActiveFromBuffer([...toolCallsBuffer]);
      }
      const parsed = parseToolResult(result);
      const snapshot = parsed?.graphSnapshot;
      if (snapshot && typeof snapshot === "object" && !Array.isArray(snapshot)) {
        applyGraphSnapshot(snapshot);
      }
      break;
    }
    case "subkani_task_start": {
      const { task } = event.data as { task?: string };
      if (task) thinking.subKaniTaskStart(task);
      break;
    }
    case "subkani_tool_call_start": {
      const {
        task,
        id,
        name,
        arguments: args,
      } = event.data as {
        task?: string;
        id: string;
        name: string;
        arguments?: string;
      };
      if (!task) break;
      const newToolCall: ToolCall = { id, name, arguments: parseToolArguments(args) };
      thinking.subKaniToolCallStart(task, newToolCall);
      break;
    }
    case "subkani_tool_call_end": {
      const { task, id, result } = event.data as {
        task?: string;
        id: string;
        result: string;
      };
      if (!task) break;
      thinking.subKaniToolCallEnd(task, id, result);
      break;
    }
    case "subkani_task_end": {
      const { task, status } = event.data as { task?: string; status?: string };
      if (!task) break;
      thinking.subKaniTaskEnd(task, status);
      break;
    }
    case "strategy_update": {
      const { step, graphId } = event.data as {
        graphId?: string;
        step: {
          stepId: string;
          type: string;
          kind?: string;
          displayName: string;
          searchName?: string;
          transformName?: string;
          operator?: string;
          leftStepId?: string;
          rightStepId?: string;
          inputStepId?: string;
          primaryInputStepId?: string;
          secondaryInputStepId?: string;
          parameters?: Record<string, unknown>;
          name?: string | null;
          description?: string | null;
          recordType?: string;
          graphId?: string;
          graphName?: string;
        };
      };
      const targetGraphId = graphId || step?.graphId || strategyIdAtStart || null;
      if (!targetGraphId || !step) break;
      if (strategyIdAtStart && targetGraphId !== strategyIdAtStart) break;

      const snapshot = strategyRef.current;
      if (
        !pendingUndoSnapshotRef.current &&
        snapshot &&
        snapshot.id === targetGraphId
      ) {
        pendingUndoSnapshotRef.current = snapshot;
      }
      if (step?.name || step?.description || step?.recordType) {
        setStrategyMeta({
          name: step.graphName ?? step.name ?? undefined,
          description: step.description ?? undefined,
          recordType: step.recordType ?? undefined,
        });
      }
      if (!strategyIdAtStart || strategyIdAtStart === targetGraphId) {
        addStep({
          id: step.stepId,
          kind: (step.kind ?? step.type) as StrategyStep["kind"],
          displayName: step.displayName || step.kind || step.type,
          recordType: step.recordType ?? undefined,
          searchName: step.searchName,
          operator: (step.operator as StrategyStep["operator"]) ?? undefined,
          primaryInputStepId:
            step.primaryInputStepId || step.leftStepId || step.inputStepId,
          secondaryInputStepId: step.secondaryInputStepId || step.rightStepId,
          parameters: step.parameters,
        });
        appliedSnapshotRef.current = true;
      }
      break;
    }
    case "graph_snapshot": {
      const { graphSnapshot } = event.data as {
        graphSnapshot?: Record<string, unknown>;
      };
      if (graphSnapshot) applyGraphSnapshot(graphSnapshot);
      break;
    }
    case "strategy_link": {
      const { graphId, wdkStrategyId, wdkUrl, name, description, strategySnapshotId } =
        event.data as {
          graphId?: string;
          wdkStrategyId?: number;
          wdkUrl?: string;
          name?: string;
          description?: string;
          strategySnapshotId?: string;
        };
      const targetGraphId = graphId || strategySnapshotId || strategyIdAtStart;
      if (strategyIdAtStart && targetGraphId !== strategyIdAtStart) break;
      const isActive = !!targetGraphId;
      if (isActive && wdkStrategyId)
        setWdkInfo(wdkStrategyId, wdkUrl, name, description);
      if (isActive && targetGraphId) {
        setStrategyMeta({
          name: name ?? undefined,
          description: description ?? undefined,
        });
      }
      if (isActive && currentStrategy) {
        addExecutedStrategy({
          ...currentStrategy,
          name: name ?? currentStrategy.name,
          description: description ?? currentStrategy.description,
          wdkStrategyId: wdkStrategyId ?? currentStrategy.wdkStrategyId,
          wdkUrl: wdkUrl ?? currentStrategy.wdkUrl,
          updatedAt: new Date().toISOString(),
        });
      } else if (targetGraphId) {
        getStrategy(targetGraphId)
          .then((full) => addExecutedStrategy(full))
          .catch(() => {});
      }
      break;
    }
    case "strategy_meta": {
      const { graphId, name, description, recordType, graphName } = event.data as {
        graphId?: string;
        name?: string;
        description?: string;
        recordType?: string | null;
        graphName?: string;
      };
      const targetGraphId = graphId || strategyIdAtStart;
      if (!targetGraphId) break;
      if (strategyIdAtStart && targetGraphId !== strategyIdAtStart) break;
      setStrategyMeta({
        name: name ?? graphName ?? undefined,
        description: description ?? undefined,
        recordType: recordType ?? undefined,
      });
      break;
    }
    case "strategy_cleared": {
      const { graphId } = event.data as { graphId?: string };
      const targetGraphId = graphId || strategyIdAtStart;
      if (!targetGraphId || (strategyIdAtStart && targetGraphId !== strategyIdAtStart))
        break;
      if (!strategyIdAtStart || targetGraphId === strategyIdAtStart) clearStrategy();
      break;
    }
    case "error": {
      const { error } = event.data as { error: string };
      const assistantMessage: Message = {
        role: "assistant",
        content: `⚠️ Error: ${error}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
      break;
    }
    case "unknown":
    default:
      break;
  }
}
