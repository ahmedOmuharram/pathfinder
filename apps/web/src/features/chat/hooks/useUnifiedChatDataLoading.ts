import { useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import { useQuery } from "@tanstack/react-query";
import { useEventCallback } from "usehooks-ts";
import { APIError } from "@/lib/api/http";
import { getStrategy } from "@/lib/api/strategies";
import { mergeMessages } from "@/features/chat/utils/mergeMessages";
import { InteractivePlanSchema } from "@/lib/types/plan";
import type { Message, Strategy } from "@pathfinder/shared";
import type { useThinkingState } from "@/features/chat/hooks/useThinkingState";
import type { StreamingSession } from "@/features/chat/streaming/StreamingSession";
import { useSessionStore } from "@/state/useSessionStore";
import { usePlanStore } from "@/state/usePlanStore";
import type {
  PipelinePhase,
  PhaseStatus,
  TimedPipelinePhase,
} from "@/state/usePlanStore";

// Type guards for server-validated pipeline phase/status values.
const VALID_PHASES: ReadonlySet<string> = new Set<PipelinePhase>([
  "scoping",
  "discovery",
  "planning",
  "execution",
  "verification",
  "completed",
]);
const TIMED_PHASES: ReadonlySet<string> = new Set<TimedPipelinePhase>([
  "scoping",
  "discovery",
  "planning",
  "execution",
  "verification",
]);
const VALID_STATUSES: ReadonlySet<string> = new Set<PhaseStatus>([
  "started",
  "completed",
  "failed",
  "awaiting_approval",
  "awaiting_input",
]);
function isPipelinePhase(v: string): v is PipelinePhase {
  return VALID_PHASES.has(v);
}
function isTimedPipelinePhase(v: string): v is TimedPipelinePhase {
  return TIMED_PHASES.has(v);
}
function isPhaseStatus(v: string): v is PhaseStatus {
  return VALID_STATUSES.has(v);
}
function asRecord(v: unknown): Record<string, unknown> | null {
  if (v == null || typeof v !== "object" || Array.isArray(v)) return null;
  return v as Record<string, unknown>;
}

// Role allow-list for Message[] narrowing. Using a Set avoids the
// tautology warning that fires when TypeScript narrows `m.role` across a
// chain of `===` comparisons whose union exactly equals the role type.
const MESSAGE_ROLES: ReadonlySet<string> = new Set(["user", "assistant"]);

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
  /**
   * When true, the caller has an active SSE stream; REST snapshots must not
   * replace locally-held streaming messages (Race D guard). Non-message
   * state (plan, strategy meta, model id, phase timings) is still restored
   * so REST remains useful for page-reload recovery.
   */
  isStreaming?: boolean;
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
  isStreaming = false,
}: UseUnifiedChatDataLoadingParams): UseUnifiedChatDataLoadingReturn {
  const authVersion = useSessionStore((s) => s.authVersion);
  const authRefreshed = useSessionStore((s) => s.authRefreshed);
  const { applyThinkingPayload } = thinking;

  const [applied, setApplied] = useState<string | null>(null);

  // Wrap in useEventCallback so the function identity is stable across
  // renders and invocation from the render body does not trigger the
  // "ref access during render" lint error (the callback runs in an event
  // handler / microtask frame owned by usehooks-ts, not during render).
  const applyStrategy = useEventCallback((strategy: Strategy) => {
    // Skip message merge during active streaming; messages are authoritative
    // from the SSE stream while it is in-flight. Non-message state (plan,
    // strategy meta, model id, phase timings) is still restored so REST
    // remains useful for page-reload recovery.
    if (!isStreaming) {
      const incoming = (strategy.messages ?? []).filter((m): m is Message =>
        MESSAGE_ROLES.has(m.role),
      );
      setMessages((prev) => mergeMessages(prev, incoming));
    }
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
        ...(strategy.recordType != null
          ? { recordType: strategy.recordType }
          : {}),
        siteId: strategy.siteId,
      });
    }

    // Restore plan state from REST response for page-reload resumability.
    if (strategy.activePlan != null) {
      const parsed = InteractivePlanSchema.safeParse(strategy.activePlan);
      if (parsed.success) {
        usePlanStore.getState().setPlan(parsed.data);
      }
    }
    const cs = strategy.conversationState;
    if (cs != null) {
      // Restore every known phase timing first so that elapsed-time labels
      // and phase history reappear without waiting for a fresh SSE stream.
      const rawTimings = asRecord(cs["phaseTimings"]);
      if (rawTimings != null) {
        for (const [phaseName, timingRaw] of Object.entries(rawTimings)) {
          const timing = asRecord(timingRaw);
          if (timing == null) continue;
          if (!isTimedPipelinePhase(phaseName)) continue;
          const statusVal = timing["status"];
          if (typeof statusVal !== "string" || !isPhaseStatus(statusVal))
            continue;
          const emittedAt = timing["emittedAt"];
          const phaseStartedAt = timing["phaseStartedAt"];
          const phaseCompletedAt = timing["phaseCompletedAt"];
          const durationMs = timing["durationMs"];
          usePlanStore.getState().setPhase(phaseName, statusVal, {
            emittedAt: typeof emittedAt === "string" ? emittedAt : null,
            phaseStartedAt:
              typeof phaseStartedAt === "string" ? phaseStartedAt : null,
            phaseCompletedAt:
              typeof phaseCompletedAt === "string" ? phaseCompletedAt : null,
            durationMs: typeof durationMs === "number" ? durationMs : null,
          });
        }
      }
      // Then set the current phase/status as the "active" marker so it is
      // applied last and wins over any phaseTimings entry for the same phase.
      const phase = cs["currentPhase"];
      const status = cs["phaseStatus"];
      if (
        typeof phase === "string"
        && typeof status === "string"
        && isPipelinePhase(phase)
        && isPhaseStatus(status)
      ) {
        usePlanStore.getState().setPhase(phase, status);
      }
    }
  });

  const { data, isPending } = useQuery({
    queryKey: ["chat-data-loading", strategyId, authVersion] as const,
    queryFn: async () => {
      const strategy = await getStrategy(strategyId!);
      return strategy;
    },
    enabled: strategyId != null && strategyId !== "" && authRefreshed,
    staleTime: Infinity,
    gcTime: 0,
    retry: (failureCount, err) => {
      if (
        err instanceof APIError
        && (err.status === 404 || err.status === 403)
      )
        return false;
      return failureCount < 1;
    },
    throwOnError: (err) => {
      if (
        err instanceof APIError
        && (err.status === 404 || err.status === 403)
      ) {
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

  // Render-body detection: when `data` changes to a new strategy/auth tuple,
  // apply it exactly once. `applyStrategy` is a `useEventCallback` so its
  // invocation from the render body does not produce the "ref access during
  // render" lint error, and `setApplied` is a safe render-body setState
  // because the guard ensures it runs only on a real key change.
  if (data != null && applied !== `${strategyId}:${authVersion}`) {
    setApplied(`${strategyId}:${authVersion}`);
    setApiError(null);
    applyStrategy(data);
  }

  return { isLoading: isPending && strategyId != null && strategyId !== "" };
}
