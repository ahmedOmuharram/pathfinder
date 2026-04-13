import type {
  AssistantMessage,
  UserMessage,
} from "@pathfinder/shared";
import type { ChatEventContext } from "./handleChatEvent.types";
import type {
  MessageStartData,
  UserMessageData,
  AssistantDeltaData,
  AssistantMessageData,
} from "@/lib/sse_events";
import { DEFAULT_STREAM_NAME } from "@pathfinder/shared";
import { usePlanStore } from "@/state/usePlanStore";
import {
  resolveAssistantIndexByMessageId,
  rememberAssistantIndex,
  hasAssistantPayload,
  buildAssistantIdentityFields,
} from "./handleChatEvent.messageHelpers";

// Re-export metadata events so the dispatcher can import everything from here.
export {
  handleCitationsEvent,
  handlePlanningArtifactEvent,
  handleProblemFrameEvent,
  handleReasoningEvent,
  handleOptimizationProgressEvent,
  handleModelSelectedEvent,
  handleTokenUsagePartialEvent,
  handleMessageEndEvent,
  handleErrorEvent,
} from "./handleChatEvent.messageMetadataEvents";

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
    for (let i = prev.length - 1; i >= 0; i--) {
      const msg = prev[i];
      if (msg?.role !== "user") continue;
      if (msg.content === content) return prev;
      break;
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
      stepCount: strategy?.steps.length ?? 0,
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
      if (existing?.role !== "assistant") return prev;
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
        if (existing?.role !== "assistant") return prev;
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
