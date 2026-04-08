import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { useQuery } from "@tanstack/react-query";
import { APIError } from "@/lib/api/http";
import { getStrategy } from "@/lib/api/strategies";
import { mergeMessages } from "@/features/chat/utils/mergeMessages";
import type { Message, Strategy } from "@pathfinder/shared";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { useSessionStore } from "@/state/useSessionStore";

interface UseUnifiedChatDataLoadingParams {
  strategyId: string | null;
  sessionRef: { current: StreamingSession | null };
  setMessages: Dispatch<SetStateAction<Message[]>>;
  setApiError: Dispatch<SetStateAction<string | null>>;
  setSelectedModelId: Dispatch<SetStateAction<string | null>>;
  thinking: ReturnType<typeof useThinkingState>;
  setStrategy: (strategy: Strategy) => void;
  setStrategyMeta: (meta: {
    name?: string;
    description?: string | null;
    recordType?: string | null;
    siteId?: string;
  }) => void;
  onStrategyNotFound?: () => void;
}

interface UseUnifiedChatDataLoadingReturn {
  isLoading: boolean;
}

export function useUnifiedChatDataLoading({
  strategyId,
  sessionRef,
  setMessages,
  setApiError,
  setSelectedModelId,
  thinking,
  setStrategy,
  setStrategyMeta,
  onStrategyNotFound,
}: UseUnifiedChatDataLoadingParams): UseUnifiedChatDataLoadingReturn {
  const authVersion = useSessionStore((s) => s.authVersion);
  const { applyThinkingPayload } = thinking;

  const [applied, setApplied] = useState<string | null>(null);

  const applyStrategy = (strategy: Strategy) => {
    const incoming = (strategy.messages ?? []).filter(
      (m): m is Message => m.role === "user" || m.role === "assistant",
    );
    setMessages((prev) => mergeMessages(prev, incoming));
    const planningPhase = strategy.pipeline?.["planning"] as
      | { modelId?: string }
      | undefined;
    const restoredModelId = planningPhase?.modelId;
    if (restoredModelId != null && restoredModelId !== "")
      setSelectedModelId(restoredModelId);
    if (strategy.thinking != null) {
      applyThinkingPayload(strategy.thinking);
    }
    if (strategy.id !== "" && sessionRef.current?.snapshotApplied !== true) {
      setStrategy(strategy);
      setStrategyMeta({
        name: strategy.name,
        ...(strategy.recordType != null ? { recordType: strategy.recordType } : {}),
        siteId: strategy.siteId,
      });
    }
  };

  const { data, isPending } = useQuery({
    queryKey: ["chat-data-loading", strategyId, authVersion] as const,
    queryFn: async () => {
      const strategy = await getStrategy(strategyId!);
      return strategy;
    },
    enabled: strategyId != null && strategyId !== "",
    staleTime: Infinity,
    gcTime: 0,
    retry: (failureCount, err) => {
      if (err instanceof APIError && (err.status === 404 || err.status === 403)) return false;
      return failureCount < 1;
    },
    throwOnError: (err) => {
      if (err instanceof APIError && (err.status === 404 || err.status === 403)) {
        onStrategyNotFound?.();
      } else {
        setApiError(
          err instanceof APIError
            ? `Could not load conversation (${err.status}).`
            : "Could not load conversation.",
        );
      }
      return false;
    },
  });

  if (data && applied !== `${strategyId}:${authVersion}`) {
    setApplied(`${strategyId}:${authVersion}`);
    setApiError(null);
    applyStrategy(data);
  }

  return { isLoading: isPending && strategyId != null && strategyId !== "" };
}
