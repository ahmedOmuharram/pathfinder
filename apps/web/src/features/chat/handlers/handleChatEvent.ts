import type { Dispatch, SetStateAction } from "react";
import type { Message, ToolCall } from "@pathfinder/shared";
import type { ChatSSEEvent } from "@/features/chat/sse_events";
import type { StrategyStep, StrategyWithMeta } from "@/types/strategy";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { MutableRef } from "@/shared/types/refs";

type Thinking = ReturnType<typeof useThinkingState>;

export type ChatEventContext = {
  siteId: string;
  strategyIdAtStart: string | null;
  toolCallsBuffer: ToolCall[];
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
    description?: string | null
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
  parseToolResult: (result?: string | null) => { graphSnapshot?: unknown } | null;
  applyGraphSnapshot: (graphSnapshot: any) => void;
  getStrategy: (id: string) => Promise<StrategyWithMeta>;
};

export function handleChatEvent(ctx: ChatEventContext, event: ChatSSEEvent) {
  const {
    siteId,
    strategyIdAtStart,
    toolCallsBuffer,
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
    case "assistant_message": {
      const content = (event.data as { content?: string })?.content || "";
      if (content) {
        const subKaniActivity = thinking.snapshotSubKaniActivity();
        const assistantMessage: Message = {
          role: "assistant",
          content,
          toolCalls: toolCallsBuffer.length > 0 ? [...toolCallsBuffer] : undefined,
          subKaniActivity,
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
        pendingUndoSnapshotRef.current = null;
        toolCallsBuffer.length = 0;
      }
      break;
    }
    case "tool_call_start": {
      const { id, name, arguments: args } = event.data as {
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
      if (snapshot && typeof snapshot === "object") {
        applyGraphSnapshot(snapshot as any);
      }
      break;
    }
    case "subkani_task_start": {
      const { task } = event.data as { task?: string };
      if (task) thinking.subKaniTaskStart(task);
      break;
    }
    case "subkani_tool_call_start": {
      const { task, id, name, arguments: args } = event.data as {
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
      const { task, id, result } = event.data as { task?: string; id: string; result: string };
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
      if (!pendingUndoSnapshotRef.current && snapshot && snapshot.id === targetGraphId) {
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
      const { graphSnapshot } = event.data as { graphSnapshot?: Record<string, unknown> };
      if (graphSnapshot) applyGraphSnapshot(graphSnapshot as any);
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
      if (isActive && wdkStrategyId) setWdkInfo(wdkStrategyId, wdkUrl, name, description);
      if (isActive && targetGraphId) {
        setStrategyMeta({ name: name ?? undefined, description: description ?? undefined });
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
      if (!targetGraphId || (strategyIdAtStart && targetGraphId !== strategyIdAtStart)) break;
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

