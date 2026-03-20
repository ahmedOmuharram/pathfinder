import type {
  Message,
  OptimizationProgressData,
  OptimizationTrial,
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
      const msg = prev[i];
      if (msg?.role !== "user") continue;
      if (msg.content === content) return prev;
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
  const messageId = data.messageId;
  const delta =
    typeof data.delta === "string"
      ? data.delta
      : Array.isArray(data.delta)
        ? (data.delta as string[]).join("")
        : "";
  if (delta === "") return;

  if (
    ctx.streamState.streamingAssistantIndex === null ||
    (messageId != null &&
      messageId !== "" &&
      ctx.streamState.streamingAssistantMessageId !== messageId)
  ) {
    ctx.streamState.streamingAssistantIndex = -1;
    ctx.streamState.streamingAssistantMessageId = messageId ?? null;

    const assistantMessage: Message = {
      role: "assistant",
      content: delta,
      ...(ctx.streamState.currentModelId != null
        ? { modelId: ctx.streamState.currentModelId }
        : {}),
      ...(ctx.streamState.optimizationProgress != null
        ? { optimizationProgress: ctx.streamState.optimizationProgress }
        : {}),
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
    if (existing?.role !== "assistant") return prev;
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
    (messageId == null ||
      messageId === "" ||
      ctx.streamState.streamingAssistantMessageId === messageId)
  ) {
    ctx.session.consumeUndoSnapshot();
    ctx.setMessages((prev) => {
      const idx = resolveAssistantIndex(ctx.streamState.streamingAssistantIndex, prev);
      if (idx === null) return prev;
      const next = [...prev];
      const existing = next[idx];
      if (existing?.role !== "assistant") return prev;
      const mergedReasoning = finalReasoning ?? existing.reasoning;
      const mergedOptimization = finalOptimization ?? existing.optimizationProgress;
      next[idx] = {
        ...existing,
        content: finalContent !== "" ? finalContent : existing.content,
        ...(finalToolCalls != null
          ? { toolCalls: finalToolCalls }
          : existing.toolCalls != null
            ? { toolCalls: existing.toolCalls }
            : {}),
        ...(subKaniActivity != null ? { subKaniActivity } : {}),
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
        ...(mergedReasoning != null && mergedReasoning !== ""
          ? { reasoning: mergedReasoning }
          : {}),
        ...(mergedOptimization != null
          ? { optimizationProgress: mergedOptimization }
          : {}),
      };
      return next;
    });
  } else if (finalContent) {
    const assistantMessage: Message = {
      role: "assistant",
      content: finalContent,
      ...(ctx.streamState.currentModelId != null
        ? { modelId: ctx.streamState.currentModelId }
        : {}),
      ...(finalToolCalls != null ? { toolCalls: finalToolCalls } : {}),
      ...(subKaniActivity != null ? { subKaniActivity } : {}),
      ...(finalCitations != null ? { citations: finalCitations } : {}),
      ...(finalArtifacts != null ? { planningArtifacts: finalArtifacts } : {}),
      ...(finalReasoning != null && finalReasoning !== ""
        ? { reasoning: finalReasoning }
        : {}),
      ...(finalOptimization != null ? { optimizationProgress: finalOptimization } : {}),
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
    const existing = prev[idx];
    if (existing == null) return prev;
    next[idx] = { ...existing, optimizationProgress: normalizedProgress };
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
      const msg = updated[i];
      if (msg?.role === "user" && msg.tokenUsage == null) {
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
  const total = typeof data["totalTokens"] === "number" ? data["totalTokens"] : 0;
  if (total <= 0) return;

  const usage: TokenUsage = {
    promptTokens: Number(data["promptTokens"]) || 0,
    completionTokens: Number(data["completionTokens"]) || 0,
    totalTokens: total,
    cachedTokens: Number(data["cachedTokens"]) || 0,
    toolCallCount: Number(data["toolCallCount"]) || 0,
    registeredToolCount: Number(data["registeredToolCount"]) || 0,
    llmCallCount: Number(data["llmCallCount"]) || 0,
    subKaniPromptTokens: Number(data["subKaniPromptTokens"]) || 0,
    subKaniCompletionTokens: Number(data["subKaniCompletionTokens"]) || 0,
    subKaniCallCount: Number(data["subKaniCallCount"]) || 0,
    estimatedCostUsd: Number(data["estimatedCostUsd"]) || 0,
    modelId: String(data["modelId"] ?? ""),
  };

  ctx.setMessages((prev) => {
    const updated = [...prev];
    // Update last user message (may already have partial usage from token_usage_partial).
    for (let i = updated.length - 1; i >= 0; i--) {
      const msg = updated[i];
      if (msg?.role === "user") {
        updated[i] = { ...msg, tokenUsage: usage };
        break;
      }
    }
    // Update last assistant message.
    for (let i = updated.length - 1; i >= 0; i--) {
      const msg = updated[i];
      if (msg?.role === "assistant" && msg.tokenUsage == null) {
        updated[i] = { ...msg, tokenUsage: usage };
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
