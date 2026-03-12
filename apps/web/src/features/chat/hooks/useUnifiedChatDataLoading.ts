import { useCallback, useEffect, useRef, useState, startTransition } from "react";
import type { Dispatch, SetStateAction } from "react";
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
  /** Apply strategy to the graph store directly (avoids a second fetch). */
  setStrategy: (strategy: Strategy) => void;
  setStrategyMeta: (meta: {
    name?: string;
    description?: string | null;
    recordType?: string | null;
    siteId?: string;
  }) => void;
  /** Called when the strategy no longer exists (404). */
  onStrategyNotFound?: () => void;
}

export interface UseUnifiedChatDataLoadingReturn {
  /** True while the initial strategy fetch is in-flight. */
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
  const [isLoading, setIsLoading] = useState(!!strategyId);

  // Track whether the last load attempt failed (for auth retry).
  const loadFailedRef = useRef(false);
  const prevAuthVersionRef = useRef(authVersion);

  const applyStrategy = useCallback(
    (strategy: Strategy) => {
      const incoming = strategy.messages || [];
      setMessages((prev) => mergeMessages(prev, incoming));
      if (strategy.modelId) setSelectedModelId(strategy.modelId);
      if (strategy.thinking) {
        thinking.applyThinkingPayload(strategy.thinking);
      }
      // Apply the already-fetched strategy directly to the graph store
      // instead of calling loadGraph (which would re-fetch the same data).
      if (strategy.id && !sessionRef.current?.snapshotApplied) {
        setStrategy(strategy);
        setStrategyMeta({
          name: strategy.name,
          recordType: strategy.recordType ?? undefined,
          siteId: strategy.siteId,
        });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setMessages, setSelectedModelId, setStrategy, setStrategyMeta],
  );

  // Primary data loading effect — runs on strategyId change.
  useEffect(() => {
    if (!strategyId) {
      startTransition(() => setMessages([]));
      loadFailedRef.current = false;
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    let cancelled = false;

    const loadWithRetry = async () => {
      try {
        const strategy = await getStrategy(strategyId);
        if (cancelled) return;
        loadFailedRef.current = false;
        setApiError(null);
        applyStrategy(strategy);
      } catch (err) {
        if (cancelled) return;

        if (err instanceof APIError && (err.status === 404 || err.status === 403)) {
          onStrategyNotFound?.();
          setIsLoading(false);
          return;
        }

        try {
          const strategy = await getStrategy(strategyId);
          if (cancelled) return;
          loadFailedRef.current = false;
          setApiError(null);
          applyStrategy(strategy);
        } catch (retryErr) {
          if (cancelled) return;
          loadFailedRef.current = true;
          setApiError(
            retryErr instanceof APIError
              ? `Could not load conversation (${retryErr.status}).`
              : "Could not load conversation.",
          );
        }
      } finally {
        if (!cancelled) setIsLoading(false);
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

    loadFailedRef.current = false;

    let cancelled = false;
    getStrategy(strategyId)
      .then((strategy) => {
        if (cancelled) return;
        setApiError(null);
        applyStrategy(strategy);
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

  return { isLoading };
}
