"use client";

/**
 * Manages the plan→execute transition lifecycle:
 * - Opening a draft strategy (executor build)
 * - Auto-executing after the mode flips to "execute"
 * - Plan-mode streaming callbacks
 */

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { PlanningArtifact } from "@pathfinder/shared";
import { getStrategy, openStrategy } from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { useStrategyStore } from "@/state/useStrategyStore";
import { openAndHydrateDraftStrategy } from "@/features/strategy/services/openAndHydrateDraftStrategy";
import { upsertSessionArtifact } from "@/features/chat/utils/planStreamState";

export interface UseUnifiedChatPlanTransitionArgs {
  siteId: string;
  setApiError: Dispatch<SetStateAction<string | null>>;
  setChatIsStreaming: (value: boolean) => void;
  handleError: (error: unknown, fallback: string) => void;
}

export interface UnifiedChatPlanTransition {
  /** Kick off the plan→execute transition by creating a draft strategy. */
  startExecutorBuild: (messageText: string) => void;
  /** Plan-mode streaming callback: set plan session ID. */
  onPlanSessionId: (id: string) => void;
  /** Plan-mode streaming callback: upsert planning artifact. */
  onPlanningArtifactUpdate: (artifact: PlanningArtifact) => void;
  /** Plan-mode streaming callback: queue executor build after stream ends. */
  onExecutorBuildRequest: (message: string) => void;
  /** Plan-mode streaming callback: bump plan list version on title change. */
  onConversationTitleUpdate: (title: string) => void;
  /** Streaming lifecycle: called when stream completes (triggers queued executor build). */
  onStreamComplete: () => void;
  /** Streaming lifecycle: called when stream errors out. */
  onStreamError: (error: Error) => void;
  /** Session artifacts from planning-mode stream. */
  sessionArtifacts: PlanningArtifact[];
  setSessionArtifacts: Dispatch<SetStateAction<PlanningArtifact[]>>;
  /** Pending auto-execute request (exposed for the component to handle). */
  pendingAutoExecute: { strategyId: string; prompt: string } | null;
  clearPendingAutoExecute: () => void;
}

export function useUnifiedChatPlanTransition({
  siteId,
  setApiError,
  setChatIsStreaming,
  handleError,
}: UseUnifiedChatPlanTransitionArgs): UnifiedChatPlanTransition {
  const setStrategyIdGlobal = useSessionStore((s) => s.setStrategyId);
  const planSessionId = useSessionStore((s) => s.planSessionId);
  const setPlanSessionId = useSessionStore((s) => s.setPlanSessionId);
  const bumpPlanListVersion = useSessionStore((s) => s.bumpPlanListVersion);
  const linkConversation = useSessionStore((s) => s.linkConversation);

  const addStrategy = useStrategyListStore((s) => s.addStrategy);

  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const clearStrategy = useStrategyStore((s) => s.clear);

  const [sessionArtifacts, setSessionArtifacts] = useState<PlanningArtifact[]>([]);
  const [pendingExecutorBuildMessage, setPendingExecutorBuildMessage] = useState<
    string | null
  >(null);
  const [pendingAutoExecute, setPendingAutoExecute] = useState<{
    strategyId: string;
    prompt: string;
  } | null>(null);
  const executorBuildTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // --- Executor build ---

  const startExecutorBuild = useCallback(
    (messageText: string) => {
      openAndHydrateDraftStrategy({
        siteId,
        open: () => openStrategy({ siteId }),
        getStrategy,
        nowIso: () => new Date().toISOString(),
        setStrategyId: setStrategyIdGlobal,
        addStrategy,
        clearStrategy,
        setStrategy,
        setStrategyMeta,
        onHydrateSuccess: (full) => {
          if (planSessionId) {
            linkConversation(planSessionId, full.id);
          }
          setPendingAutoExecute({
            strategyId: full.id,
            prompt: messageText,
          });
        },
        onHydrateError: (error) => {
          setApiError(toUserMessage(error, "Failed to load the new strategy."));
        },
      }).catch((error) => {
        setApiError(toUserMessage(error, "Failed to open a new strategy."));
      });
    },
    [
      addStrategy,
      clearStrategy,
      linkConversation,
      planSessionId,
      setApiError,
      setStrategy,
      setStrategyIdGlobal,
      setStrategyMeta,
      siteId,
    ],
  );

  // --- Plan-mode callbacks ---

  const onPlanSessionId = useCallback(
    (id: string) => setPlanSessionId(id),
    [setPlanSessionId],
  );

  const onPlanningArtifactUpdate = useCallback((artifact: PlanningArtifact) => {
    setSessionArtifacts((prev) => upsertSessionArtifact(prev, artifact));
  }, []);

  const onExecutorBuildRequest = useCallback((message: string) => {
    setPendingExecutorBuildMessage(message);
  }, []);

  const onConversationTitleUpdate = useCallback(
    (_title: string) => {
      bumpPlanListVersion();
    },
    [bumpPlanListVersion],
  );

  // --- Streaming lifecycle ---

  const onStreamComplete = useCallback(() => {
    setChatIsStreaming(false);
    setPendingExecutorBuildMessage((msg) => {
      if (msg) {
        executorBuildTimerRef.current = setTimeout(() => startExecutorBuild(msg), 1000);
      }
      return null;
    });
  }, [setChatIsStreaming, startExecutorBuild]);

  const onStreamError = useCallback(
    (error: Error) => {
      setChatIsStreaming(false);
      handleError(error, "Unable to reach the API.");
      setPendingExecutorBuildMessage(null);
    },
    [setChatIsStreaming, handleError],
  );

  // Clean up pending executor build timer on unmount.
  useEffect(() => {
    return () => {
      if (executorBuildTimerRef.current) clearTimeout(executorBuildTimerRef.current);
    };
  }, []);

  const clearPendingAutoExecute = useCallback(() => setPendingAutoExecute(null), []);

  return {
    startExecutorBuild,
    onPlanSessionId,
    onPlanningArtifactUpdate,
    onExecutorBuildRequest,
    onConversationTitleUpdate,
    onStreamComplete,
    onStreamError,
    sessionArtifacts,
    setSessionArtifacts,
    pendingAutoExecute,
    clearPendingAutoExecute,
  };
}
