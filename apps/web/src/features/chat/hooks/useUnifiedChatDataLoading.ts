import { useEffect, startTransition } from "react";
import type { Dispatch, SetStateAction } from "react";
import { getPlanSession, getStrategy } from "@/lib/api/client";
import { mergeMessages } from "@/features/chat/utils/mergeMessages";
import type { ChatMode, Message, PlanningArtifact } from "@pathfinder/shared";
import type { StrategyWithMeta } from "@/features/strategy/types";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { usePrevious } from "@/lib/hooks/usePrevious";

interface UseUnifiedChatDataLoadingParams {
  chatMode: ChatMode;
  planSessionId: string | null;
  strategyId: string | null;
  isStreaming: boolean;
  sessionRef: { current: StreamingSession | null };
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setSessionArtifacts: Dispatch<SetStateAction<PlanningArtifact[]>>;
  setApiError: Dispatch<SetStateAction<string | null>>;
  setSelectedModelId: Dispatch<SetStateAction<string | null>>;
  thinking: ReturnType<typeof useThinkingState>;
  handleError: (error: unknown, fallback: string) => void;
  loadGraph: (graphId: string) => void;
}

export function useUnifiedChatDataLoading({
  chatMode,
  planSessionId,
  strategyId,
  isStreaming,
  sessionRef,
  setMessages,
  setSessionArtifacts,
  setApiError,
  setSelectedModelId,
  thinking,
  handleError,
  loadGraph,
}: UseUnifiedChatDataLoadingParams) {
  const prevPlanSessionId = usePrevious(planSessionId);

  useEffect(() => {
    if (chatMode !== "plan") return;
    if (!planSessionId) {
      if (isStreaming) return;
      startTransition(() => setMessages([]));
      return;
    }
    if (isStreaming) return;

    if (prevPlanSessionId !== planSessionId) {
      startTransition(() => {
        setMessages([]);
        setSessionArtifacts([]);
        setApiError(null);
      });
      thinking.reset();
    }

    getPlanSession(planSessionId)
      .then((ps) => {
        setMessages((prev) => mergeMessages(prev, ps.messages || []));
        setSessionArtifacts(ps.planningArtifacts || []);
        if (ps.modelId) setSelectedModelId(ps.modelId);
        if (ps.thinking) {
          thinking.applyThinkingPayload(ps.thinking);
        }
      })
      .catch((error) => {
        handleError(error, "Failed to load plan.");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatMode, planSessionId, isStreaming]);

  useEffect(() => {
    if (chatMode !== "execute") return;
    if (!strategyId) {
      if (isStreaming) return;
      startTransition(() => setMessages([]));
      return;
    }
    if (isStreaming) return;

    getStrategy(strategyId)
      .then((strategy: StrategyWithMeta) => {
        setMessages((prev) => mergeMessages(prev, strategy.messages || []));
        if (strategy.modelId) setSelectedModelId(strategy.modelId);
        if (!isStreaming && strategy.thinking) {
          thinking.applyThinkingPayload(strategy.thinking);
        }
        if (strategy.id && !sessionRef.current?.snapshotApplied) {
          loadGraph(strategy.id);
        }
      })
      .catch((err) => {
        console.warn("[UnifiedChat] Failed to fetch strategy messages:", err);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatMode, strategyId, isStreaming]);
}
