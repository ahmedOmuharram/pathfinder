import type {
  AssistantMessage,
  OptimizationProgressData,
  OptimizationTrial,
  TokenUsage,
} from "@pathfinder/shared";
import type { ChatEventContext } from "./handleChatEvent.types";
import type {
  CitationsData,
  PlanningArtifactData,
  ProblemFrameData,
  ReasoningData,
  ModelSelectedData,
  TokenUsagePartialData,
  MessageEndData,
  ErrorData,
} from "@/lib/sse_events";
import { usePlanStore } from "@/state/usePlanStore";
import { resolveAssistantIndexByMessageId } from "./handleChatEvent.messageHelpers";

export function handleCitationsEvent(ctx: ChatEventContext, data: CitationsData) {
  const citations = data.citations;
  if (!Array.isArray(citations)) return;
  for (const c of citations) {
    ctx.citationsBuffer.push(c);
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

  ctx.setMessages((prev) => {
    const activeMessageId = ctx.streamState.streamingAssistantMessageId ?? null;
    let idx = resolveAssistantIndexByMessageId(
      ctx.streamState,
      prev,
      activeMessageId,
    );
    idx ??= resolveAssistantIndexByMessageId(
      ctx.streamState,
      prev,
      ctx.streamState.lastAssistantMessageId ?? null,
    );
    if (idx == null || idx < 0) {
      idx = ctx.streamState.turnAssistantIndex ?? null;
    }
    if (idx == null || idx < 0 || idx >= prev.length) return prev;
    const existing = prev[idx];
    if (existing?.role !== "assistant") return prev;
    const next = [...prev];
    next[idx] = { ...existing, optimizationProgress: normalizedProgress };
    return next;
  });
}

export function handleModelSelectedEvent(
  ctx: ChatEventContext,
  data: ModelSelectedData,
) {
  ctx.streamState.pipeline = data.pipeline;

  const modelId = data.pipeline.planning.modelId;
  if (typeof modelId === "string") {
    ctx.setSelectedModelId?.(modelId || null);
    ctx.streamState.currentModelId = modelId || null;

    // Retroactively stamp modelId on assistant messages that were created
    // before this event arrived (e.g. assistant_delta processed first due to
    // SSE subscription timing or operation recovery race).
    if (modelId !== "") {
      ctx.setMessages((prev) => {
        const needsStamp = prev.some(
          (msg) => msg.role === "assistant" && (msg.modelId == null || msg.modelId === ""),
        );
        if (!needsStamp) return prev;
        return prev.map((msg) => {
          if (msg.role !== "assistant") return msg;
          if (msg.modelId != null && msg.modelId !== "") return msg;
          return { ...msg, modelId };
        });
      });
    }
  }
}

export function handleTokenUsagePartialEvent(
  ctx: ChatEventContext,
  data: TokenUsagePartialData,
) {
  const promptTokens = typeof data.promptTokens === "number" ? data.promptTokens : 0;
  const registeredToolCount =
    typeof data.registeredToolCount === "number" ? data.registeredToolCount : 0;
  if (promptTokens <= 0) return;

  ctx.setMessages((prev) => {
    const updated = [...prev];
    for (let i = updated.length - 1; i >= 0; i--) {
      const msg = prev[i];
      if (msg?.role !== "user") continue;
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
  const traceId = typeof data["traceId"] === "string" && data["traceId"] !== ""
    ? data["traceId"]
    : null;

  const total = typeof data["totalTokens"] === "number" ? data["totalTokens"] : 0;

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
