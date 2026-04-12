import type {
  AssistantMessage,
  Message,
  PlanningArtifact,
  ProblemFrame,
  UserMessage,
  OptimizationProgressData,
  OptimizationTrial,
  TokenUsage,
  ToolCall,
} from "@pathfinder/shared";
import type { ChatEventContext } from "./handleChatEvent.types";
import type {
  MessageStartData,
  UserMessageData,
  AssistantDeltaData,
  AssistantMessageData,
  CitationsData,
  PlanningArtifactData,
  ProblemFrameData,
  ReasoningData,
  ModelSelectedData,
  TokenUsagePartialData,
  MessageEndData,
  ErrorData,
} from "@/lib/sse_events";
import { DEFAULT_STREAM_NAME } from "@pathfinder/shared";
import type { StreamSessionState } from "./handleChatEvent.types";
import { usePlanStore } from "@/state/usePlanStore";

/**
 * Resolve the current streaming assistant message index with fallback.
 *
 * If the tracked index is stale (null or negative), falls back to the
 * last message if it's an assistant message. Returns null when no valid
 * index can be resolved.
 */
function resolveAssistantIndex(
  streamingIndex: number | null,
  messages: readonly Message[],
): number | null {
  let idx = streamingIndex;
  if (
    (idx === null || idx < 0) &&
    messages[messages.length - 1]?.role === "assistant"
  ) {
    idx = messages.length - 1;
  }
  if (idx === null || idx < 0 || idx >= messages.length) return null;
  return idx;
}

function rememberAssistantIndex(
  streamState: StreamSessionState,
  messageId: string | null,
  index: number,
): void {
  if (messageId != null && messageId !== "") {
    streamState.assistantMessageIndices[messageId] = index;
    streamState.lastAssistantMessageId = messageId;
  }
  streamState.streamingAssistantIndex = index;
  streamState.turnAssistantIndex = index;
}

function resolveAssistantIndexByMessageId(
  streamState: StreamSessionState,
  messages: readonly Message[],
  messageId: string | null,
): number | null {
  if (messageId != null && messageId !== "") {
    const remembered = streamState.assistantMessageIndices[messageId];
    if (remembered != null) {
      const msg = messages[remembered];
      if (msg != null && msg.role === "assistant" && msg.messageId === messageId) {
        return remembered;
      }
      delete streamState.assistantMessageIndices[messageId];
    }

    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const msg = messages[i];
      if (msg?.role !== "assistant") continue;
      if (msg.messageId !== messageId) continue;
      streamState.assistantMessageIndices[messageId] = i;
      return i;
    }

    return null;
  }

  return resolveAssistantIndex(streamState.streamingAssistantIndex, messages);
}

function hasAssistantPayload(
  content: string,
  toolCalls?: ToolCall[],
  citations?: CitationsData["citations"],
  artifacts?: PlanningArtifact[],
  problemFrame?: ProblemFrame | null,
  reasoning?: string,
  optimization?: OptimizationProgressData,
): boolean {
  return (
    content.trim() !== "" ||
    (toolCalls?.length ?? 0) > 0 ||
    (citations?.length ?? 0) > 0 ||
    (artifacts?.length ?? 0) > 0 ||
    problemFrame != null ||
    (reasoning?.trim().length ?? 0) > 0 ||
    optimization != null
  );
}

function buildAssistantIdentityFields(
  streamState: StreamSessionState,
  messageId: string | null,
): Partial<AssistantMessage> {
  const fields: Partial<AssistantMessage> = {};
  if (messageId != null && messageId !== "") {
    fields.messageId = messageId;
  }
  if (streamState.messageGroupId != null && streamState.messageGroupId !== "") {
    fields.messageGroupId = streamState.messageGroupId;
  }
  if (
    streamState.currentPhase === "discovery" ||
    streamState.currentPhase === "scoping" ||
    streamState.currentPhase === "planning" ||
    streamState.currentPhase === "execution" ||
    streamState.currentPhase === "verification"
  ) {
    fields.phase = streamState.currentPhase;
  }
  return fields;
}

/**
 * Handle `user_message` events from the Redis stream catch-up.
 *
 * During normal streaming the user message is added locally by
 * `handleSendMessage` before the stream starts.  But during
 * **operation recovery** (page refresh / reconnect), the catch-up
 * replays events from Redis — including the user_message — and
 * we must append it so `mergeMessages` sees a complete conversation.
 */
export function handleUserMessageEvent(ctx: ChatEventContext, data: UserMessageData) {
  const content = typeof data.content === "string" ? data.content : "";
  if (!content) return;
  usePlanStore.getState().clearThoughts();
  usePlanStore.getState().clearPhaseTimings();
  usePlanStore.getState().clearPhase();

  ctx.setMessages((prev) => {
    // De-duplicate: skip if the last user message has the same content
    // (can happen if data-loading and recovery both add it).
    for (let i = prev.length - 1; i >= 0; i--) {
      const msg = prev[i];
      if (msg?.role !== "user") continue;
      if (msg.content === content) return prev;
      break; // Only check the most recent user message
    }
    const userMessage: UserMessage = {
      role: "user",
      content,
      timestamp: new Date().toISOString(),
    };
    return [...prev, userMessage];
  });
}

export function handleMessageStartEvent(ctx: ChatEventContext, data: MessageStartData) {
  const { strategyId, strategy } = data;

  if (strategyId != null && strategyId !== "") {
    ctx.setStrategyId(strategyId);
    ctx.addStrategy({
      id: strategyId,
      name: strategy?.name ?? DEFAULT_STREAM_NAME,
      ...(strategy?.title != null
        ? { title: strategy.title }
        : strategy?.name != null
          ? { title: strategy.name }
          : { title: DEFAULT_STREAM_NAME }),
      siteId: ctx.siteId,
      recordType: strategy?.recordType ?? null,
      steps: strategy?.steps ?? [],
      rootStepId: strategy?.rootStepId ?? null,
      stepCount: strategy?.steps?.length ?? 0,
      ...(strategy?.wdkStrategyId != null
        ? { wdkStrategyId: strategy.wdkStrategyId }
        : {}),
      isSaved: strategy?.isSaved === true,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });
    ctx.loadGraph(strategyId);
  }

  if (strategy) {
    ctx.setStrategy(strategy);
    ctx.setStrategyMeta({
      name: strategy.name,
      ...(strategy.recordType != null ? { recordType: strategy.recordType } : {}),
      siteId: strategy.siteId,
    });
  }
}

export function handleAssistantDeltaEvent(
  ctx: ChatEventContext,
  data: AssistantDeltaData,
) {
  const messageId =
    typeof data.messageId === "string" && data.messageId !== ""
      ? data.messageId
      : ctx.streamState.streamingAssistantMessageId;
  if (typeof data.messageGroupId === "string" && data.messageGroupId !== "") {
    ctx.streamState.messageGroupId = data.messageGroupId;
  }
  if (typeof data.phase === "string" && data.phase !== "") {
    ctx.streamState.currentPhase = data.phase;
  }
  const delta =
    typeof data.delta === "string"
      ? data.delta
      : Array.isArray(data.delta)
        ? (data.delta as string[]).join("")
        : "";
  if (delta === "") return;
  ctx.streamState.streamingAssistantMessageId = messageId ?? null;
  ctx.thinking.setActiveMessage(messageId ?? null);
  const identityFields = buildAssistantIdentityFields(
    ctx.streamState,
    messageId ?? null,
  );

  ctx.setMessages((prev) => {
    const idx = resolveAssistantIndexByMessageId(
      ctx.streamState,
      prev,
      messageId ?? null,
    );
    if (idx !== null) {
      const existing = prev[idx];
      if (existing == null || existing.role !== "assistant") return prev;
      const next = [...prev];
      next[idx] = {
        ...existing,
        content: (existing.content || "") + delta,
        ...identityFields,
      };
      rememberAssistantIndex(ctx.streamState, messageId ?? null, idx);
      return next;
    }

    const assistantMessage: AssistantMessage = {
      role: "assistant",
      content: delta,
      ...identityFields,
      ...(ctx.streamState.currentModelId != null
        ? { modelId: ctx.streamState.currentModelId }
        : {}),
      ...(ctx.streamState.optimizationProgress != null
        ? { optimizationProgress: ctx.streamState.optimizationProgress }
        : {}),
      timestamp: new Date().toISOString(),
    };
    const next = [...prev, assistantMessage];
    rememberAssistantIndex(ctx.streamState, messageId ?? null, next.length - 1);
    return next;
  });
}

export function handleAssistantMessageEvent(
  ctx: ChatEventContext,
  data: AssistantMessageData,
) {
  const messageId =
    typeof data.messageId === "string" && data.messageId !== ""
      ? data.messageId
      : ctx.streamState.streamingAssistantMessageId;
  if (typeof data.messageGroupId === "string" && data.messageGroupId !== "") {
    ctx.streamState.messageGroupId = data.messageGroupId;
  }
  if (typeof data.phase === "string" && data.phase !== "") {
    ctx.streamState.currentPhase = data.phase;
  }
  const finalContent =
    typeof data.content === "string"
      ? data.content
      : Array.isArray(data.content)
        ? (data.content as string[]).join("")
        : "";

  const finalToolCalls =
    ctx.toolCallsBuffer.length > 0 ? [...ctx.toolCallsBuffer] : undefined;
  const finalCitations =
    ctx.citationsBuffer.length > 0 ? [...ctx.citationsBuffer] : undefined;
  const finalArtifacts =
    ctx.planningArtifactsBuffer.length > 0
      ? [...ctx.planningArtifactsBuffer]
      : undefined;
  const finalProblemFrame = ctx.problemFrameBuffer ?? undefined;
  const finalReasoning = ctx.streamState.reasoning ?? undefined;
  const finalOptimization = ctx.streamState.optimizationProgress ?? undefined;
  const shouldPersistMessage = hasAssistantPayload(
    finalContent,
    finalToolCalls,
    finalCitations,
    finalArtifacts,
    finalProblemFrame,
    finalReasoning,
    finalOptimization,
  );
  const shouldClearActiveMessage =
    ctx.streamState.streamingAssistantMessageId == null ||
    messageId == null ||
    ctx.streamState.streamingAssistantMessageId === messageId;

  const snapshot = ctx.session.consumeUndoSnapshot();
  if (shouldPersistMessage) {
    ctx.setMessages((prev) => {
      const idx = resolveAssistantIndexByMessageId(
        ctx.streamState,
        prev,
        messageId ?? null,
      );
      const baseFields = buildAssistantIdentityFields(
        ctx.streamState,
        messageId ?? null,
      );

      if (idx !== null) {
        const existing = prev[idx];
        if (existing == null || existing.role !== "assistant") return prev;
        const mergedReasoning = finalReasoning ?? existing.reasoning;
        const mergedOptimization = finalOptimization ?? existing.optimizationProgress;
        const mergedProblemFrame = finalProblemFrame ?? existing.problemFrame;
        const next = [...prev];
        next[idx] = {
          ...existing,
          ...baseFields,
          content: finalContent !== "" ? finalContent : existing.content,
          ...(ctx.streamState.currentModelId != null
            ? { modelId: ctx.streamState.currentModelId }
            : existing.modelId != null
              ? { modelId: existing.modelId }
              : {}),
          ...(finalToolCalls != null
            ? { toolCalls: finalToolCalls }
            : existing.toolCalls != null
              ? { toolCalls: existing.toolCalls }
              : {}),
          ...(finalCitations != null
            ? { citations: finalCitations }
            : existing.citations != null
              ? { citations: existing.citations }
              : {}),
          ...(finalArtifacts != null
            ? { planningArtifacts: finalArtifacts }
            : existing.planningArtifacts != null
              ? { planningArtifacts: existing.planningArtifacts }
              : {}),
          ...(mergedProblemFrame != null
            ? { problemFrame: mergedProblemFrame }
            : {}),
          ...(mergedReasoning != null && mergedReasoning !== ""
            ? { reasoning: mergedReasoning }
            : {}),
          ...(mergedOptimization != null
            ? { optimizationProgress: mergedOptimization }
            : {}),
        };
        rememberAssistantIndex(ctx.streamState, messageId ?? null, idx);
        if (shouldClearActiveMessage) {
          ctx.streamState.streamingAssistantIndex = null;
          ctx.streamState.streamingAssistantMessageId = null;
        }
        return next;
      }

      const assistantMessage: AssistantMessage = {
        role: "assistant",
        content: finalContent,
        ...baseFields,
        ...(ctx.streamState.currentModelId != null
          ? { modelId: ctx.streamState.currentModelId }
          : {}),
        ...(finalToolCalls != null ? { toolCalls: finalToolCalls } : {}),
        ...(finalCitations != null ? { citations: finalCitations } : {}),
        ...(finalArtifacts != null ? { planningArtifacts: finalArtifacts } : {}),
        ...(finalProblemFrame != null ? { problemFrame: finalProblemFrame } : {}),
        ...(finalReasoning != null && finalReasoning !== ""
          ? { reasoning: finalReasoning }
          : {}),
        ...(finalOptimization != null ? { optimizationProgress: finalOptimization } : {}),
        timestamp: new Date().toISOString(),
      };
      const next = [...prev, assistantMessage];
      const appendedIndex = next.length - 1;
      rememberAssistantIndex(ctx.streamState, messageId ?? null, appendedIndex);
      if (snapshot) {
        ctx.setUndoSnapshots((prevSnapshots) => ({
          ...prevSnapshots,
          [appendedIndex]: snapshot,
        }));
      }
      if (shouldClearActiveMessage) {
        ctx.streamState.streamingAssistantIndex = null;
        ctx.streamState.streamingAssistantMessageId = null;
      }
      return next;
    });
  } else if (shouldClearActiveMessage) {
    ctx.streamState.streamingAssistantIndex = null;
    ctx.streamState.streamingAssistantMessageId = null;
  }

  if (shouldClearActiveMessage) {
    ctx.streamState.streamingAssistantIndex = null;
    ctx.streamState.streamingAssistantMessageId = null;
    ctx.streamState.reasoning = null;
    ctx.toolCallsBuffer.length = 0;
    ctx.citationsBuffer.length = 0;
    ctx.planningArtifactsBuffer.length = 0;
    ctx.problemFrameBuffer = null;
    ctx.thinking.setActiveMessage(null);
  }
}

export function handleCitationsEvent(ctx: ChatEventContext, data: CitationsData) {
  const citations = data.citations;
  if (!Array.isArray(citations)) return;
  for (const c of citations) {
    if (c != null && typeof c === "object" && !Array.isArray(c)) {
      ctx.citationsBuffer.push(c);
    }
  }
}

export function handlePlanningArtifactEvent(
  ctx: ChatEventContext,
  data: PlanningArtifactData,
) {
  const artifact = data.planningArtifact;
  if (!artifact || typeof artifact !== "object" || Array.isArray(artifact)) return;
  ctx.planningArtifactsBuffer.push(artifact);
}

export function handleProblemFrameEvent(
  ctx: ChatEventContext,
  data: ProblemFrameData,
) {
  ctx.problemFrameBuffer = data.problemFrame;
}

export function handleReasoningEvent(ctx: ChatEventContext, data: ReasoningData) {
  const reasoning = data.reasoning;
  if (typeof reasoning !== "string") return;
  ctx.thinking.updateReasoning(
    reasoning,
    ctx.streamState.streamingAssistantMessageId,
  );
  ctx.streamState.reasoning = reasoning;
}

export function handleOptimizationProgressEvent(
  ctx: ChatEventContext,
  data: OptimizationProgressData,
) {
  const progressData = data;
  const previous = ctx.streamState.optimizationProgress;

  const mergedTrialsByNumber = new Map<number, OptimizationTrial>();
  for (const t of previous?.allTrials ?? previous?.recentTrials ?? []) {
    mergedTrialsByNumber.set(t.trialNumber, t);
  }
  for (const t of progressData.allTrials ?? progressData.recentTrials ?? []) {
    mergedTrialsByNumber.set(t.trialNumber, t);
  }
  const mergedAllTrials = Array.from(mergedTrialsByNumber.values()).sort(
    (a, b) => a.trialNumber - b.trialNumber,
  );

  const mergedTrials =
    mergedAllTrials.length > 0
      ? mergedAllTrials
      : (progressData.allTrials ?? progressData.recentTrials);
  const normalizedProgress: OptimizationProgressData = {
    ...progressData,
    ...(mergedTrials != null ? { allTrials: mergedTrials } : {}),
  };

  ctx.streamState.optimizationProgress = normalizedProgress;
  ctx.setOptimizationProgress(normalizedProgress);

  // Write optimization data only to the current turn's assistant message.
  // Never fall back to a generic "last assistant" scan, which would leak
  // live progress into a previous conversation turn.
  ctx.setMessages((prev) => {
    const activeMessageId = ctx.streamState.streamingAssistantMessageId ?? null;
    let idx = resolveAssistantIndexByMessageId(
      ctx.streamState,
      prev,
      activeMessageId,
    );
    if (idx == null) {
      idx = resolveAssistantIndexByMessageId(
        ctx.streamState,
        prev,
        ctx.streamState.lastAssistantMessageId ?? null,
      );
    }
    if (idx == null || idx < 0) {
      idx = ctx.streamState.turnAssistantIndex ?? null;
    }
    if (idx == null || idx < 0 || idx >= prev.length) return prev;
    const existing = prev[idx];
    if (existing == null || existing.role !== "assistant") return prev;
    const next = [...prev];
    next[idx] = { ...existing, optimizationProgress: normalizedProgress };
    return next;
  });
}

export function handleModelSelectedEvent(
  ctx: ChatEventContext,
  data: ModelSelectedData,
) {
  if (data.pipeline != null) {
    ctx.streamState.pipeline = data.pipeline;
  }

  // Extract the planning model as the default representative model ID.
  const modelId = data.pipeline?.planning?.modelId;
  if (typeof modelId === "string") {
    ctx.setSelectedModelId?.(modelId || null);
    ctx.streamState.currentModelId = modelId || null;
  }
}

export function handleTokenUsagePartialEvent(
  ctx: ChatEventContext,
  data: TokenUsagePartialData,
) {
  // Attach prompt tokens to the last user message immediately, before the
  // model finishes (or even if it fails).
  const promptTokens = typeof data.promptTokens === "number" ? data.promptTokens : 0;
  const registeredToolCount =
    typeof data.registeredToolCount === "number" ? data.registeredToolCount : 0;
  if (promptTokens <= 0) return;

  ctx.setMessages((prev) => {
    const updated = [...prev];
    for (let i = updated.length - 1; i >= 0; i--) {
      const msg = prev[i];
      if (msg == null || msg.role !== "user") continue;
      if (msg.tokenUsage != null) continue;
      updated[i] = {
        ...msg,
        tokenUsage: {
          promptTokens,
          completionTokens: 0,
          totalTokens: promptTokens,
          cachedTokens: 0,
          toolCallCount: 0,
          registeredToolCount,
          llmCallCount: 0,
          estimatedCostUsd: 0,
          modelId: "",
        },
      };
      break;
    }
    return updated;
  });
}

export function handleMessageEndEvent(ctx: ChatEventContext, data: MessageEndData) {
  // Extract traceId for Langfuse feedback scoring.
  const traceId = typeof data["traceId"] === "string" && data["traceId"] !== ""
    ? data["traceId"]
    : null;

  // Attach token usage to the last user message (input cost) and assistant message (output cost).
  const total = typeof data["totalTokens"] === "number" ? data["totalTokens"] : 0;

  // Even if there are no tokens, we may still need to attach the traceId.
  if (total <= 0 && traceId == null) return;

  const usage: TokenUsage | null = total > 0 ? {
    promptTokens: Number(data["promptTokens"]) || 0,
    completionTokens: Number(data["completionTokens"]) || 0,
    totalTokens: total,
    cachedTokens: Number(data["cachedTokens"]) || 0,
    toolCallCount: Number(data["toolCallCount"]) || 0,
    registeredToolCount: Number(data["registeredToolCount"]) || 0,
    llmCallCount: Number(data["llmCallCount"]) || 0,
    estimatedCostUsd: Number(data["estimatedCostUsd"]) || 0,
    modelId: String(data["modelId"] ?? ""),
  } : null;

  ctx.setMessages((prev) => {
    const updated = [...prev];
    // Update last user message (may already have partial usage from token_usage_partial).
    if (usage != null || traceId != null) {
      for (let i = updated.length - 1; i >= 0; i--) {
        const msg = prev[i];
        if (msg?.role !== "user") continue;
        updated[i] = {
          ...msg,
          ...(usage != null ? { tokenUsage: usage } : {}),
          ...(traceId != null ? { traceId } : {}),
        };
        break;
      }
    }
    // Update last assistant message with token usage and/or traceId.
    for (let i = updated.length - 1; i >= 0; i--) {
      const msg = prev[i];
      if (msg?.role !== "assistant") continue;
      if (usage == null && traceId == null) break;
      if (msg.tokenUsage != null && traceId == null) break;
      updated[i] = {
        ...msg,
        ...(usage != null && msg.tokenUsage == null ? { tokenUsage: usage } : {}),
        ...(traceId != null ? { traceId } : {}),
      };
      break;
    }
    return updated;
  });
  if (traceId != null) {
    const planStore = usePlanStore.getState();
    if (
      planStore.activePlan != null &&
      planStore.activePlanMessageGroupId != null &&
      planStore.activePlanMessageGroupId === ctx.streamState.messageGroupId
    ) {
      planStore.setPlanTraceContext({
        traceId,
        messageGroupId: planStore.activePlanMessageGroupId,
      });
    }
  }
  ctx.thinking.setActiveMessage(null);
}

export function handleErrorEvent(ctx: ChatEventContext, data: ErrorData) {
  const { error } = data;
  const assistantMessage: AssistantMessage = {
    role: "assistant",
    content: `⚠️ Error: ${error}`,
    timestamp: new Date().toISOString(),
  };
  ctx.setMessages((prev) => [...prev, assistantMessage]);
  ctx.thinking.setActiveMessage(null);
  ctx.onApiError?.(error);
}
