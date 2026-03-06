import { useCallback, useEffect, useRef, startTransition } from "react";
import type { Dispatch, SetStateAction } from "react";
import { APIError, getStrategy } from "@/lib/api/client";
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
  loadGraph: (graphId: string) => void;
  /** Called when the strategy no longer exists (404). */
  onStrategyNotFound?: () => void;
}

export function useUnifiedChatDataLoading({
  strategyId,
  sessionRef,
  setMessages,
  setApiError,
  setSelectedModelId,
  thinking,
  loadGraph,
  onStrategyNotFound,
}: UseUnifiedChatDataLoadingParams) {
  const authVersion = useSessionStore((s) => s.authVersion);

  // Track whether the last load attempt failed (for auth retry).
  const loadFailedRef = useRef(false);
  const prevAuthVersionRef = useRef(authVersion);

  const applyStrategy = useCallback(
    (strategy: Strategy, targetStrategyId: string) => {
      const incoming = strategy.messages || [];
      console.log("[DataLoading] applyStrategy", {
        strategyId: targetStrategyId,
        incomingMessages: incoming.length,
        hasModelId: !!strategy.modelId,
        hasThinking: !!strategy.thinking,
      });
      setMessages((prev) => {
        const result = mergeMessages(prev, incoming);
        console.log("[DataLoading] mergeMessages", {
          prevLen: prev.length,
          incomingLen: incoming.length,
          resultLen: result.length,
        });
        return result;
      });
      if (strategy.modelId) setSelectedModelId(strategy.modelId);
      if (strategy.thinking) {
        thinking.applyThinkingPayload(strategy.thinking);
      }
      if (strategy.id && !sessionRef.current?.snapshotApplied) {
        loadGraph(strategy.id);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setMessages, setSelectedModelId, loadGraph],
  );

  // Primary data loading effect — runs on strategyId change.
  useEffect(() => {
    if (!strategyId) {
      startTransition(() => setMessages([]));
      loadFailedRef.current = false;
      return;
    }

    let cancelled = false;

    const loadWithRetry = async () => {
      console.log("[DataLoading] loadWithRetry START", { strategyId });
      try {
        const strategy = await getStrategy(strategyId);
        if (cancelled) return;
        console.log("[DataLoading] getStrategy OK", {
          strategyId,
          messageCount: strategy.messages?.length ?? "null/undefined",
          name: strategy.name,
        });
        loadFailedRef.current = false;
        setApiError(null);
        applyStrategy(strategy, strategyId);
      } catch (err) {
        if (cancelled) return;

        if (err instanceof APIError && err.status === 404) {
          console.warn("[DataLoading] Strategy not found (404), clearing selection");
          onStrategyNotFound?.();
          return;
        }

        console.warn("[DataLoading] First load FAILED, retrying:", err);
        try {
          const strategy = await getStrategy(strategyId);
          if (cancelled) return;
          console.log("[DataLoading] Retry OK", {
            strategyId,
            messageCount: strategy.messages?.length ?? "null/undefined",
          });
          loadFailedRef.current = false;
          setApiError(null);
          applyStrategy(strategy, strategyId);
        } catch (retryErr) {
          if (cancelled) return;
          console.error("[DataLoading] Retry ALSO failed:", retryErr);
          loadFailedRef.current = true;
          setApiError(
            retryErr instanceof APIError
              ? `Could not load conversation (${retryErr.status}).`
              : "Could not load conversation.",
          );
        }
      }
    };

    void loadWithRetry();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategyId]);

  // Auth-cookie retry: if a previous load failed and the auth cookie was
  // refreshed (signaled by authVersion bump), retry loading.
  useEffect(() => {
    if (prevAuthVersionRef.current === authVersion) return;
    prevAuthVersionRef.current = authVersion;
    if (!strategyId || !loadFailedRef.current) return;

    console.log("[DataLoading] Retrying after auth refresh", { strategyId });
    loadFailedRef.current = false;

    let cancelled = false;
    getStrategy(strategyId)
      .then((strategy) => {
        if (cancelled) return;
        console.log("[DataLoading] Auth-retry OK", {
          strategyId,
          messageCount: strategy.messages?.length ?? "null/undefined",
        });
        setApiError(null);
        applyStrategy(strategy, strategyId);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("[DataLoading] Auth-retry failed:", err);
        loadFailedRef.current = true;
      });

    return () => {
      cancelled = true;
    };
  }, [authVersion, strategyId, applyStrategy, setApiError]);
}
