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
  setStrategy: (strategy: Strategy) => void;
  setStrategyMeta: (meta: {
    name?: string;
    description?: string | null;
    recordType?: string | null;
    siteId?: string;
  }) => void;
  onStrategyNotFound?: () => void;
}

export interface UseUnifiedChatDataLoadingReturn {
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

  // Track whether the last load failed so auth-retry only fires when needed.
  const loadFailedRef = useRef(false);
  // Track the previous authVersion to distinguish initial mount from auth bumps.
  const prevAuthVersionRef = useRef(authVersion);

  const applyStrategy = useCallback(
    (strategy: Strategy) => {
      const incoming = strategy.messages || [];
      setMessages((prev) => mergeMessages(prev, incoming));
      if (strategy.modelId) setSelectedModelId(strategy.modelId);
      if (strategy.thinking) {
        thinking.applyThinkingPayload(strategy.thinking);
      }
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

  // Single unified loading effect — handles both initial load and auth retry.
  // Including authVersion in deps means this re-runs on auth refresh, but we
  // guard the auth-retry path with loadFailedRef so a successful load is not
  // re-fetched when auth changes.
  useEffect(() => {
    const isAuthRetry = prevAuthVersionRef.current !== authVersion;
    prevAuthVersionRef.current = authVersion;

    if (!strategyId) {
      startTransition(() => setMessages([]));
      loadFailedRef.current = false;
      setIsLoading(false);
      return;
    }

    // On auth bump, only retry if the previous load actually failed.
    if (isAuthRetry && !loadFailedRef.current) return;

    setIsLoading(true);
    let cancelled = false;

    const load = async () => {
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

        // Single retry
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

    void load();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategyId, authVersion]);

  return { isLoading };
}
