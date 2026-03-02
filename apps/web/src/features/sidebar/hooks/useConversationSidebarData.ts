"use client";

/**
 * Data-fetching and list-building logic for the conversation sidebar.
 *
 * Owns plan/strategy items, syncing state, search query, and the
 * merged+filtered conversation list.
 */

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  startTransition,
} from "react";
import {
  APIError,
  getPlanSession,
  listPlans,
  syncWdkStrategies,
} from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/useStrategyStore";
import type { StrategyListItem } from "@/features/sidebar/utils/strategyItems";
import type { PlanSessionSummary } from "@pathfinder/shared";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

export interface UseConversationSidebarDataArgs {
  siteId: string;
  reportError: (message: string) => void;
}

export interface ConversationSidebarData {
  /** Filtered conversation list (by search query). */
  filtered: ConversationItem[];
  /** Whether there are any conversations at all (ignoring search). */
  hasConversations: boolean;
  query: string;
  setQuery: (q: string) => void;
  isSyncing: boolean;
  refreshPlans: () => Promise<void>;
  refreshStrategies: () => Promise<void>;
  handleManualRefresh: () => Promise<void>;
  /** Exposed for the actions hook to perform optimistic plan-list updates. */
  planItems: PlanSessionSummary[];
  setPlanItems: Dispatch<SetStateAction<PlanSessionSummary[]>>;
  /** Exposed for the actions hook to perform optimistic strategy-list updates. */
  strategyItems: StrategyListItem[];
  setStrategyItems: Dispatch<SetStateAction<StrategyListItem[]>>;
  /** Shared error handler for auth-aware plan errors. */
  handlePlanError: (error: unknown, fallback: string) => void;
}

export function useConversationSidebarData({
  siteId,
  reportError,
}: UseConversationSidebarDataArgs): ConversationSidebarData {
  // --- Store selectors ---
  const planSessionId = useSessionStore((s) => s.planSessionId);
  const setPlanSessionId = useSessionStore((s) => s.setPlanSessionId);
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyId = useSessionStore((s) => s.setStrategyId);
  const authToken = useSessionStore((s) => s.authToken);
  const setAuthToken = useSessionStore((s) => s.setAuthToken);
  const linkedConversations = useSessionStore((s) => s.linkedConversations);
  const planListVersion = useSessionStore((s) => s.planListVersion);

  const draftStrategy = useStrategyStore((s) => s.strategy);

  // --- Local state ---
  const [planItems, setPlanItems] = useState<PlanSessionSummary[]>([]);
  const [strategyItems, setStrategyItems] = useState<StrategyListItem[]>([]);
  const [query, setQuery] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);

  // --- Error helpers ---
  const handlePlanError = useCallback(
    (error: unknown, fallback: string) => {
      if (error instanceof APIError && error.status === 401) {
        if (!authToken) {
          setPlanItems([]);
          return;
        }
        setAuthToken(null);
        setPlanSessionId(null);
        setPlanItems([]);
        reportError("Session expired. Refresh to start a new plan.");
        return;
      }
      reportError(toUserMessage(error, fallback));
    },
    [authToken, reportError, setAuthToken, setPlanSessionId],
  );

  // --- Data fetching ---
  const refreshPlans = useCallback(async () => {
    if (!authToken) {
      setPlanItems([]);
      return;
    }
    try {
      const sessions = await listPlans(siteId);
      // Include the active plan even if server hides empty plans
      if (planSessionId && !sessions.some((p) => p.id === planSessionId)) {
        const active = await getPlanSession(planSessionId).catch((err) => {
          console.error("[useConversationSidebarData.getPlanSession]", err);
          return null;
        });
        if (active) {
          setPlanItems([
            {
              id: active.id,
              siteId: active.siteId,
              title: active.title || "New Conversation",
              createdAt: active.createdAt,
              updatedAt: active.updatedAt,
            },
            ...sessions,
          ]);
          return;
        }
        // Plan session no longer exists — clear the stale reference.
        setPlanSessionId(null);
      }
      setPlanItems(sessions);
    } catch (error) {
      setPlanItems([]);
      handlePlanError(error, "Failed to load plans.");
    }
  }, [authToken, handlePlanError, planSessionId, setPlanSessionId, siteId]);

  // Guard against concurrent sync calls (e.g. two useEffects firing on mount).
  const syncInFlight = useRef(false);

  const refreshStrategies = useCallback(() => {
    if (syncInFlight.current) return Promise.resolve();
    syncInFlight.current = true;
    return syncWdkStrategies(siteId)
      .then((strategies) => {
        const now = new Date().toISOString();
        const items: StrategyListItem[] = strategies.map((s) => ({
          id: s.id,
          name: s.name,
          updatedAt: s.updatedAt ?? now,
          siteId: s.siteId,
          wdkStrategyId: s.wdkStrategyId,
          isSaved: s.isSaved ?? false,
        }));
        setStrategyItems(items);
      })
      .catch((err) => {
        console.warn("[ConversationSidebar] Failed to sync strategies:", err);
      })
      .finally(() => {
        syncInFlight.current = false;
      });
  }, [siteId]);

  const handleManualRefresh = useCallback(async () => {
    setIsSyncing(true);
    try {
      await Promise.all([refreshPlans(), refreshStrategies()]);
    } finally {
      setIsSyncing(false);
    }
  }, [refreshPlans, refreshStrategies]);

  // Ensure there's always an active conversation (strategy).
  // If no strategy is selected, pick the most recent one.
  const ensureActiveConversation = useCallback(async () => {
    if (!authToken) return;
    // Already have a conversation selected
    if (strategyId) return;
    // Legacy: plan session is selected — don't interfere
    if (planSessionId) return;
    // Wait for strategies to load, then select the most recent
    if (strategyItems.length > 0) {
      const sorted = [...strategyItems].sort(
        (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
      );
      const mostRecent = sorted[0];
      setStrategyId(mostRecent.id);
    }
  }, [authToken, strategyId, planSessionId, strategyItems, setStrategyId]);

  // --- Effects ---

  // Refresh both on mount / auth / site change
  useEffect(() => {
    startTransition(() => {
      void refreshPlans();
      void refreshStrategies();
    });
  }, [refreshPlans, refreshStrategies]);

  // Re-fetch plans when planListVersion bumps (after new plan creation / title change)
  useEffect(() => {
    if (planListVersion > 0) void refreshPlans();
  }, [planListVersion, refreshPlans]);

  // Re-fetch strategies when draft strategy changes
  useEffect(() => {
    void refreshStrategies();
  }, [draftStrategy?.id, draftStrategy?.updatedAt, refreshStrategies]);

  // Ensure there's always an active conversation selected
  useEffect(() => {
    startTransition(() => {
      ensureActiveConversation();
    });
  }, [ensureActiveConversation]);

  // --- Build merged conversation list ---
  const linkedPlanIds = useMemo(
    () => new Set(Object.keys(linkedConversations)),
    [linkedConversations],
  );

  const conversations: ConversationItem[] = useMemo(() => {
    // Plans that haven't graduated (i.e. aren't linked to a strategy)
    const plans: ConversationItem[] = planItems
      .filter((p) => !linkedPlanIds.has(p.id))
      .map((p) => ({
        id: p.id,
        kind: "plan" as const,
        title: p.title || "New Conversation",
        updatedAt: p.updatedAt,
        siteId: p.siteId,
      }));

    // Also show the current active plan optimistically if not yet in the list
    if (planSessionId && !linkedPlanIds.has(planSessionId)) {
      const exists = plans.some((p) => p.id === planSessionId);
      if (!exists) {
        const now = new Date().toISOString();
        plans.unshift({
          id: planSessionId,
          kind: "plan",
          title: "New Conversation",
          updatedAt: now,
          siteId,
        });
      }
    }

    const strategies: ConversationItem[] = strategyItems.map((s) => ({
      id: s.id,
      kind: "strategy" as const,
      title: s.name,
      updatedAt: s.updatedAt,
      siteId: s.siteId,
      strategyItem: s,
    }));

    // Merge and sort by updatedAt descending
    return [...plans, ...strategies].sort(
      (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
    );
  }, [planItems, strategyItems, linkedPlanIds, planSessionId, siteId]);

  // Filter
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, query]);

  return {
    filtered,
    hasConversations: conversations.length > 0,
    query,
    setQuery,
    isSyncing,
    refreshPlans,
    refreshStrategies,
    handleManualRefresh,
    planItems,
    setPlanItems,
    strategyItems,
    setStrategyItems,
    handlePlanError,
  };
}
