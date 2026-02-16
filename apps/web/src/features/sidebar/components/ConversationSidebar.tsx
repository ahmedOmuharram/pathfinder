"use client";

/**
 * ConversationSidebar — unified sidebar that merges plan sessions and strategies
 * into a single chronologically sorted list. Replaces the old separate
 * PlansSidebar + StrategySidebar + sidebar tabs.
 */

import { useCallback, useEffect, useMemo, useState, startTransition } from "react";
import {
  APIError,
  createStrategy,
  deletePlanSession,
  deleteStrategy,
  getPlanSession,
  getStrategy,
  listPlans,
  openPlanSession,
  syncWdkStrategies,
  updatePlanSession,
  updateStrategy as updateStrategyApi,
} from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { useStrategyStore } from "@/state/useStrategyStore";
import { SitePicker } from "@/features/sites/components/SitePicker";
import type { StrategyListItem } from "@/features/sidebar/utils/strategyItems";
import { buildDuplicatePlan } from "@/features/sidebar/utils/duplicatePlan";
import {
  type DuplicateModalState,
  applyDuplicateLoadFailure,
  applyDuplicateLoadSuccess,
  initDuplicateModal,
} from "@/features/sidebar/utils/duplicateModalState";
import { runDeleteStrategyWorkflow } from "@/features/sidebar/services/strategySidebarWorkflows";
import type { PlanSessionSummary } from "@pathfinder/shared";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { ConversationListItem } from "@/features/sidebar/components/ConversationListItem";
import { DeleteConversationModal } from "@/features/sidebar/components/DeleteConversationModal";
import { DuplicateStrategyModal } from "@/features/sidebar/components/DuplicateStrategyModal";

// Props

interface ConversationSidebarProps {
  siteId: string;
  onToast?: (toast: {
    type: "success" | "error" | "warning" | "info";
    message: string;
  }) => void;
}

export function ConversationSidebar({ siteId, onToast }: ConversationSidebarProps) {
  // Global state
  const planSessionId = useSessionStore((s) => s.planSessionId);
  const setPlanSessionId = useSessionStore((s) => s.setPlanSessionId);
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyId = useSessionStore((s) => s.setStrategyId);
  const setSelectedSite = useSessionStore((s) => s.setSelectedSite);
  const authToken = useSessionStore((s) => s.authToken);
  const setAuthToken = useSessionStore((s) => s.setAuthToken);
  const chatIsStreaming = useSessionStore((s) => s.chatIsStreaming);
  const linkedConversations = useSessionStore((s) => s.linkedConversations);
  const planListVersion = useSessionStore((s) => s.planListVersion);
  const bumpPlanListVersion = useSessionStore((s) => s.bumpPlanListVersion);

  const graphValidationStatus = useStrategyListStore((s) => s.graphValidationStatus);
  const removeStrategy = useStrategyListStore((s) => s.removeStrategy);

  const draftStrategy = useStrategyStore((s) => s.strategy);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const clearStrategy = useStrategyStore((s) => s.clear);

  // Local state
  const [planItems, setPlanItems] = useState<PlanSessionSummary[]>([]);
  const [strategyItems, setStrategyItems] = useState<StrategyListItem[]>([]);
  const [query, setQuery] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<ConversationItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [duplicateModal, setDuplicateModal] = useState<DuplicateModalState | null>(
    null,
  );
  /** ID of the conversation item currently being renamed inline. */
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  // Error helpers
  const reportError = useCallback(
    (message: string) => onToast?.({ type: "error", message }),
    [onToast],
  );
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

  // Data fetching
  const refreshPlans = useCallback(async () => {
    if (!authToken) {
      setPlanItems([]);
      return;
    }
    try {
      const sessions = await listPlans(siteId);
      // Include the active plan even if server hides empty plans
      if (planSessionId && !sessions.some((p) => p.id === planSessionId)) {
        const active = await getPlanSession(planSessionId).catch(() => null);
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
      }
      setPlanItems(sessions);
    } catch (error) {
      setPlanItems([]);
      handlePlanError(error, "Failed to load plans.");
    }
  }, [authToken, handlePlanError, planSessionId, siteId]);

  const refreshStrategies = useCallback(() => {
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
      });
  }, [siteId]);

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

  // Ensure there's always an active plan session
  const ensureActivePlan = useCallback(async () => {
    if (!authToken) return;
    if (planSessionId) return;
    // Don't create a new plan if a strategy is currently selected
    if (strategyId) return;
    const existing = await listPlans(siteId).catch((error) => {
      handlePlanError(error, "Failed to load plans.");
      return [];
    });
    if (existing.length > 0) {
      setPlanItems(existing);
      setPlanSessionId(existing[0].id);
      return;
    }
    try {
      const res = await openPlanSession({ siteId, title: "New Conversation" });
      setPlanSessionId(res.planSessionId);
      await refreshPlans();
    } catch (error) {
      handlePlanError(error, "Failed to open a new plan.");
    }
  }, [
    authToken,
    handlePlanError,
    planSessionId,
    strategyId,
    refreshPlans,
    setPlanSessionId,
    siteId,
  ]);

  useEffect(() => {
    startTransition(() => {
      ensureActivePlan();
    });
  }, [ensureActivePlan]);

  // Build merged conversation list
  const linkedStrategyIds = useMemo(
    () => new Set(Object.values(linkedConversations)),
    [linkedConversations],
  );
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

  // Selection logic
  const activeId = strategyId || planSessionId || null;

  const handleSelect = useCallback(
    (item: ConversationItem) => {
      if (item.kind === "plan") {
        setStrategyId(null); // clears strategyId so the panel switches to plan mode
        clearStrategy();
        setPlanSessionId(item.id);
      } else {
        // Strategy — directly hydrate by local strategyId.
        // The sidebar is populated from the sync response, so the strategy
        // is guaranteed to exist in the DB.  If it somehow doesn't (race /
        // DB reset mid-session), just refresh.
        const si = item.strategyItem;
        if (!si) return;
        setStrategyId(si.id);
        clearStrategy();
        getStrategy(si.id)
          .then((full) => {
            setStrategy(full);
            setStrategyMeta({
              name: full.name,
              recordType: full.recordType ?? undefined,
              siteId: full.siteId,
            });
          })
          .catch((err) => {
            setStrategyId(null);
            reportError(toUserMessage(err, "Couldn't load strategy. Refreshing list."));
            void refreshStrategies();
          });
      }
    },
    [
      clearStrategy,
      setPlanSessionId,
      setStrategyId,
      setStrategy,
      setStrategyMeta,
      reportError,
      refreshStrategies,
    ],
  );

  // New conversation
  const handleNewConversation = useCallback(async () => {
    try {
      const res = await openPlanSession({ siteId, title: "New Conversation" });
      setStrategyId(null);
      clearStrategy();
      setPlanSessionId(res.planSessionId);
      const now = new Date().toISOString();
      setPlanItems((prev) => [
        {
          id: res.planSessionId,
          siteId,
          title: "New Conversation",
          createdAt: now,
          updatedAt: now,
        },
        ...prev.filter((p) => p.id !== res.planSessionId),
      ]);
      void refreshPlans();
    } catch (error) {
      handlePlanError(error, "Failed to open a new conversation.");
    }
  }, [
    siteId,
    setStrategyId,
    clearStrategy,
    setPlanSessionId,
    refreshPlans,
    handlePlanError,
  ]);

  // Delete conversation
  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      if (deleteTarget.kind === "plan") {
        await deletePlanSession(deleteTarget.id).catch((error) => {
          handlePlanError(error, "Failed to delete conversation.");
        });
        const wasActive = planSessionId === deleteTarget.id;
        if (wasActive) setPlanSessionId(null);
        await refreshPlans();
        if (wasActive) {
          try {
            const res = await openPlanSession({ siteId, title: "New Conversation" });
            setPlanSessionId(res.planSessionId);
            await refreshPlans();
          } catch (error) {
            handlePlanError(error, "Failed to open a new conversation.");
          }
        }
      } else {
        // Strategy delete
        const si = deleteTarget.strategyItem;
        if (si) {
          await runDeleteStrategyWorkflow({
            item: si,
            currentStrategyId: strategyId || null,
            setStrategyItems,
            clearStrategy,
            removeStrategy,
            setStrategyId,
            setDeleteError: () => {},
            deleteStrategyApi: deleteStrategy,
            refreshStrategies,
            reportError: (msg) => reportError(msg),
          });
        }
      }
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  }, [
    deleteTarget,
    planSessionId,
    strategyId,
    siteId,
    handlePlanError,
    setPlanSessionId,
    setStrategyId,
    clearStrategy,
    removeStrategy,
    refreshPlans,
    refreshStrategies,
    reportError,
  ]);

  // Strategy-specific actions

  const startRename = useCallback((item: ConversationItem) => {
    setRenamingId(item.id);
    setRenameValue(item.title);
  }, []);

  const commitRename = useCallback(
    async (item: ConversationItem) => {
      const next = renameValue.trim();
      if (!next || next === item.title) {
        setRenamingId(null);
        return;
      }
      try {
        if (item.kind === "plan") {
          await updatePlanSession(item.id, { title: next });
          bumpPlanListVersion();
          void refreshPlans();
        } else {
          await updateStrategyApi(item.id, { name: next });
          void refreshStrategies();
        }
      } catch (err) {
        reportError(toUserMessage(err, "Failed to rename."));
      }
      setRenamingId(null);
    },
    [renameValue, bumpPlanListVersion, refreshPlans, refreshStrategies, reportError],
  );

  const handleDuplicate = useCallback(
    async (strategyIdToDuplicate: string, name: string, description: string) => {
      const baseStrategy = await getStrategy(strategyIdToDuplicate);
      const plan = buildDuplicatePlan({ baseStrategy, name, description });
      await createStrategy({
        name,
        siteId: baseStrategy.siteId,
        plan,
      });
      void refreshStrategies();
    },
    [refreshStrategies],
  );

  const handleToggleSaved = useCallback(
    async (si: StrategyListItem) => {
      const nextSaved = !si.isSaved;
      try {
        await updateStrategyApi(si.id, { isSaved: nextSaved });
        // Optimistically update the item in the list.
        setStrategyItems((items) =>
          items.map((item) =>
            item.id === si.id ? { ...item, isSaved: nextSaved } : item,
          ),
        );
      } catch (err) {
        reportError(
          toUserMessage(
            err,
            nextSaved ? "Failed to save strategy." : "Failed to revert to draft.",
          ),
        );
      }
    },
    [reportError],
  );

  // Render
  return (
    <div className="flex h-full min-h-0 flex-col gap-4 border-r border-slate-200 bg-white px-3 py-4">
      {/* Site picker */}
      <div>
        <SitePicker
          value={siteId}
          onChange={setSelectedSite}
          showSelect
          showAuth={false}
          showVisit
          layout="stacked"
        />
      </div>

      {/* Header + new conversation button */}
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Conversations
        </div>
        <button
          data-testid="conversations-new-button"
          type="button"
          disabled={chatIsStreaming}
          onClick={() => void handleNewConversation()}
          className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-600 hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
        >
          New Chat
        </button>
      </div>

      {/* Search */}
      <input
        data-testid="conversations-search-input"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search conversations..."
        className="w-full rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-700 placeholder:text-slate-400"
      />

      {/* Conversation list */}
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        <div className="space-y-2">
          {filtered.length === 0 && (
            <div className="text-[11px] text-slate-500">
              {query.trim()
                ? "No conversations match your search."
                : "No conversations yet. Click \u201cNew Chat\u201d to get started."}
            </div>
          )}
          {filtered.map((item) => {
            const si = item.strategyItem;
            return (
              <ConversationListItem
                key={item.id}
                item={item}
                isActive={activeId === item.id}
                isRenaming={renamingId === item.id}
                renameValue={renameValue}
                graphHasValidationIssue={Boolean(si && graphValidationStatus[si.id])}
                onRenameValueChange={setRenameValue}
                onCommitRename={(target) => {
                  void commitRename(target);
                }}
                onCancelRename={() => setRenamingId(null)}
                onSelect={handleSelect}
                onStartRename={startRename}
                onStartDelete={setDeleteTarget}
                onStartDuplicate={(strategy) => {
                  setDuplicateModal(initDuplicateModal(strategy));
                  getStrategy(strategy.id)
                    .then((loadedStrategy) => {
                      setDuplicateModal((prev) =>
                        prev ? applyDuplicateLoadSuccess(prev, loadedStrategy) : prev,
                      );
                    })
                    .catch(() => {
                      setDuplicateModal((prev) =>
                        prev ? applyDuplicateLoadFailure(prev) : prev,
                      );
                    });
                }}
                onToggleSaved={(strategy) => {
                  void handleToggleSaved(strategy);
                }}
              />
            );
          })}
        </div>
      </div>

      <DeleteConversationModal
        target={deleteTarget}
        isDeleting={isDeleting}
        onClose={() => setDeleteTarget(null)}
        onConfirmDelete={() => {
          void confirmDelete();
        }}
      />

      <DuplicateStrategyModal
        duplicateModal={duplicateModal}
        setDuplicateModal={setDuplicateModal}
        onDuplicate={handleDuplicate}
      />
    </div>
  );
}
