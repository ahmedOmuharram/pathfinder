import type {
  Citation,
  Message,
  OptimizationProgressData,
  OptimizationTrial,
  PlanningArtifact,
  SubKaniTokenUsage,
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
  ReasoningData,
  ModelSelectedData,
  TokenUsagePartialData,
  MessageEndData,
  ErrorData,
} from "@/lib/sse_events";
import { DEFAULT_STREAM_NAME } from "@pathfinder/shared";

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

export function snapshotSubKaniActivityFromBuffers(
  calls: Record<string, ToolCall[]>,
  status: Record<string, string>,
  models?: Record<string, string>,
  tokenUsage?: Record<string, SubKaniTokenUsage>,
) {
  if (Object.keys(calls).length === 0) return undefined;
  return {
    calls: { ...calls },
    status: { ...status },
    ...(models && Object.keys(models).length > 0 ? { models: { ...models } } : {}),
    ...(tokenUsage && Object.keys(tokenUsage).length > 0
      ? { tokenUsage: { ...tokenUsage } }
      : {}),
  };
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

  ctx.setMessages((prev) => {
    // De-duplicate: skip if the last user message has the same content
    // (can happen if data-loading and recovery both add it).
    for (let i = prev.length - 1; i >= 0; i--) {
      if (prev[i].role !== "user") continue;
      if (prev[i].content === content) return prev;
      break; // Only check the most recent user message
    }
    return [
      ...prev,
      {
        role: "user" as const,
        content,
        messageId: data.messageId,
        timestamp: new Date().toISOString(),
      },
    ];
  });
}

export function handleMessageStartEvent(ctx: ChatEventContext, data: MessageStartData) {
  const { strategyId, strategy } = data;

  if (strategyId) {
    ctx.setStrategyId(strategyId);
    ctx.addStrategy({
      id: strategyId,
      name: strategy?.name || DEFAULT_STREAM_NAME,
      title: strategy?.title || strategy?.name || DEFAULT_STREAM_NAME,
      siteId: ctx.siteId,
      recordType: strategy?.recordType ?? null,
      steps: strategy?.steps ?? [],
      rootStepId: strategy?.rootStepId ?? null,
      stepCount: strategy?.steps?.length ?? 0,
      wdkStrategyId: strategy?.wdkStrategyId,
      isSaved: strategy?.isSaved ?? false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });
    ctx.loadGraph(strategyId);
  }

  if (strategy) {
    ctx.setStrategy(strategy);
    ctx.setStrategyMeta({
      name: strategy.name,
      recordType: strategy.recordType ?? undefined,
      siteId: strategy.siteId,
    });
  }
}

export function handleAssistantDeltaEvent(
  ctx: ChatEventContext,
  data: AssistantDeltaData,
) {
  const messageId = data.messageId;
  const delta =
    typeof data.delta === "string"
      ? data.delta
      : Array.isArray(data.delta)
        ? (data.delta as string[]).join("")
        : data.delta
          ? String(data.delta)
          : "";
  if (!delta) return;

  if (
    ctx.streamState.streamingAssistantIndex === null ||
    (messageId && ctx.streamState.streamingAssistantMessageId !== messageId)
  ) {
    ctx.streamState.streamingAssistantIndex = -1;
    ctx.streamState.streamingAssistantMessageId = messageId || null;

    const assistantMessage: Message = {
      role: "assistant",
      content: delta,
      modelId: ctx.streamState.currentModelId ?? undefined,
      optimizationProgress: ctx.streamState.optimizationProgress ?? undefined,
      timestamp: new Date().toISOString(),
    };
    ctx.setMessages((prev) => {
      const next = [...prev, assistantMessage];
      const resolvedIdx = next.length - 1;
      // Only resolve the sentinel; in batched delivery assistant_message may
      // have already finalized and cleared this ref.
      if (ctx.streamState.streamingAssistantIndex === -1) {
        ctx.streamState.streamingAssistantIndex = resolvedIdx;
      }
      // Always track the turn-level owner so optimization_progress events
      // can find the message even after streamingAssistantIndex is cleared.
      ctx.streamState.turnAssistantIndex = resolvedIdx;
      return next;
    });
    return;
  }

  ctx.setMessages((prev) => {
    const idx = resolveAssistantIndex(ctx.streamState.streamingAssistantIndex, prev);
    if (idx === null) return prev;
    const next = [...prev];
    const existing = next[idx];
    if (!existing || existing.role !== "assistant") return prev;
    next[idx] = { ...existing, content: (existing.content || "") + delta };
    return next;
  });
}

export function handleAssistantMessageEvent(
  ctx: ChatEventContext,
  data: AssistantMessageData,
) {
  const messageId = data.messageId;
  const finalContent =
    typeof data.content === "string"
      ? data.content
      : Array.isArray(data.content)
        ? (data.content as string[]).join("")
        : data.content
          ? String(data.content)
          : "";
  const subKaniActivity = snapshotSubKaniActivityFromBuffers(
    ctx.subKaniCallsBuffer,
    ctx.subKaniStatusBuffer,
    ctx.subKaniModelsBuffer,
    ctx.subKaniTokenUsageBuffer,
  );

  const finalToolCalls =
    ctx.toolCallsBuffer.length > 0 ? [...ctx.toolCallsBuffer] : undefined;
  const finalCitations =
    ctx.citationsBuffer.length > 0 ? [...ctx.citationsBuffer] : undefined;
  const finalArtifacts =
    ctx.planningArtifactsBuffer.length > 0
      ? [...ctx.planningArtifactsBuffer]
      : undefined;
  const finalReasoning = ctx.streamState.reasoning ?? undefined;
  const finalOptimization = ctx.streamState.optimizationProgress ?? undefined;

  if (
    ctx.streamState.streamingAssistantIndex !== null &&
    (!messageId || ctx.streamState.streamingAssistantMessageId === messageId)
  ) {
    ctx.session.consumeUndoSnapshot();
    ctx.setMessages((prev) => {
      const idx = resolveAssistantIndex(ctx.streamState.streamingAssistantIndex, prev);
      if (idx === null) return prev;
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
        reasoning: finalReasoning || existing.reasoning || undefined,
        optimizationProgress:
          finalOptimization ?? existing.optimizationProgress ?? undefined,
      };
      return next;
    });
  } else if (finalContent) {
    const assistantMessage: Message = {
      role: "assistant",
      content: finalContent,
      modelId: ctx.streamState.currentModelId ?? undefined,
      toolCalls: finalToolCalls,
      subKaniActivity,
      citations: finalCitations,
      planningArtifacts: finalArtifacts,
      reasoning: finalReasoning || undefined,
      optimizationProgress: finalOptimization,
      timestamp: new Date().toISOString(),
    };
    const snapshot = ctx.session.consumeUndoSnapshot();
    ctx.setMessages((prev) => {
      const next = [...prev, assistantMessage];
      ctx.streamState.turnAssistantIndex = next.length - 1;
      if (snapshot) {
        ctx.setUndoSnapshots((prevSnapshots) => ({
          ...prevSnapshots,
          [next.length - 1]: snapshot,
        }));
      }
      return next;
    });
  } else {
    ctx.session.consumeUndoSnapshot();
  }
  // Clear streaming refs after assistant_message finalize.  Late turn-level
  // events (e.g. optimization_progress) use turnAssistantIndex instead.
  ctx.streamState.streamingAssistantIndex = null;
  ctx.streamState.streamingAssistantMessageId = null;
  ctx.streamState.reasoning = null;
  ctx.toolCallsBuffer.length = 0;
  ctx.citationsBuffer.length = 0;
  ctx.planningArtifactsBuffer.length = 0;
}

export function handleCitationsEvent(ctx: ChatEventContext, data: CitationsData) {
  const citations = data.citations;
  if (!Array.isArray(citations)) return;
  for (const c of citations) {
    if (c && typeof c === "object" && !Array.isArray(c)) {
      ctx.citationsBuffer.push(c as Citation);
    }
  }
}

export function handlePlanningArtifactEvent(
  ctx: ChatEventContext,
  data: PlanningArtifactData,
) {
  const artifact = data.planningArtifact;
  if (!artifact || typeof artifact !== "object" || Array.isArray(artifact)) return;
  ctx.planningArtifactsBuffer.push(artifact as PlanningArtifact);
}

export function handleReasoningEvent(ctx: ChatEventContext, data: ReasoningData) {
  const reasoning = data.reasoning;
  if (typeof reasoning !== "string") return;
  ctx.thinking.updateReasoning(reasoning);
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

  const normalizedProgress: OptimizationProgressData = {
    ...progressData,
    allTrials:
      mergedAllTrials.length > 0
        ? mergedAllTrials
        : (progressData.allTrials ?? progressData.recentTrials),
  };

  ctx.streamState.optimizationProgress = normalizedProgress;
  ctx.setOptimizationProgress(normalizedProgress);

  // Write optimization data only to the current turn's assistant message.
  // Never fall back to a generic "last assistant" scan, which would leak
  // live progress into a previous conversation turn.
  ctx.setMessages((prev) => {
    let idx: number | null = ctx.streamState.streamingAssistantIndex;
    if (idx == null || idx < 0) {
      idx = ctx.streamState.turnAssistantIndex ?? null;
    }
    if (
      idx == null ||
      idx < 0 ||
      idx >= prev.length ||
      prev[idx]?.role !== "assistant"
    ) {
      return prev;
    }
    const next = [...prev];
    next[idx] = { ...prev[idx], optimizationProgress: normalizedProgress };
    return next;
  });
}

export function handleModelSelectedEvent(
  ctx: ChatEventContext,
  data: ModelSelectedData,
) {
  const { modelId } = data;
  if (typeof modelId === "string") {
    ctx.setSelectedModelId?.(modelId || null);
    // Store for stamping on subsequent assistant messages in this turn.
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
      if (updated[i].role === "user" && !updated[i].tokenUsage) {
        updated[i] = {
          ...updated[i],
          tokenUsage: {
            promptTokens,
            completionTokens: 0,
            totalTokens: promptTokens,
            cachedTokens: 0,
            toolCallCount: 0,
            registeredToolCount,
            llmCallCount: 0,
            subKaniPromptTokens: 0,
            subKaniCompletionTokens: 0,
            subKaniCallCount: 0,
            estimatedCostUsd: 0,
            modelId: "",
          },
        };
        break;
      }
    }
    return updated;
  });
}

export function handleMessageEndEvent(ctx: ChatEventContext, data: MessageEndData) {
  // Attach token usage to the last user message (input cost) and assistant message (output cost).
  const total = typeof data.totalTokens === "number" ? data.totalTokens : 0;
  if (total <= 0) return;

  const usage: TokenUsage = {
    promptTokens: Number(data.promptTokens) || 0,
    completionTokens: Number(data.completionTokens) || 0,
    totalTokens: total,
    cachedTokens: Number(data.cachedTokens) || 0,
    toolCallCount: Number(data.toolCallCount) || 0,
    registeredToolCount: Number(data.registeredToolCount) || 0,
    llmCallCount: Number(data.llmCallCount) || 0,
    subKaniPromptTokens: Number(data.subKaniPromptTokens) || 0,
    subKaniCompletionTokens: Number(data.subKaniCompletionTokens) || 0,
    subKaniCallCount: Number(data.subKaniCallCount) || 0,
    estimatedCostUsd: Number(data.estimatedCostUsd) || 0,
    modelId: String(data.modelId ?? ""),
  };

  ctx.setMessages((prev) => {
    const updated = [...prev];
    // Update last user message (may already have partial usage from token_usage_partial).
    for (let i = updated.length - 1; i >= 0; i--) {
      if (updated[i].role === "user") {
        updated[i] = { ...updated[i], tokenUsage: usage };
        break;
      }
    }
    // Update last assistant message.
    for (let i = updated.length - 1; i >= 0; i--) {
      if (updated[i].role === "assistant" && !updated[i].tokenUsage) {
        updated[i] = { ...updated[i], tokenUsage: usage };
        break;
      }
    }
    return updated;
  });
}

export function handleErrorEvent(ctx: ChatEventContext, data: ErrorData) {
  const { error } = data;
  const assistantMessage: Message = {
    role: "assistant",
    content: `⚠️ Error: ${error}`,
    timestamp: new Date().toISOString(),
  };
  ctx.setMessages((prev) => [...prev, assistantMessage]);
  ctx.onApiError?.(error);
}
