"use client";

/**
 * Action handlers and modal state for the conversation sidebar.
 *
 * Handles selection, creation, rename, delete, duplicate, and
 * saved-toggle workflows. Owns all transient UI state (modals,
 * inline rename).
 */

import { type Dispatch, type SetStateAction, useCallback, useState } from "react";
import {
  createStrategy,
  deletePlanSession,
  deleteStrategy,
  getStrategy,
  openStrategy,
  updatePlanSession,
  updateStrategy as updateStrategyApi,
} from "@/lib/api/client";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { useStrategyStore } from "@/state/useStrategyStore";
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

export interface UseConversationSidebarActionsArgs {
  siteId: string;
  reportError: (message: string) => void;
  handlePlanError: (error: unknown, fallback: string) => void;
  refreshPlans: () => Promise<void>;
  refreshStrategies: () => Promise<void>;
  setPlanItems: Dispatch<SetStateAction<PlanSessionSummary[]>>;
  setStrategyItems: Dispatch<SetStateAction<StrategyListItem[]>>;
}

export interface ConversationSidebarActions {
  /** Currently active conversation ID (strategy or plan). */
  activeId: string | null;

  // Selection
  handleSelect: (item: ConversationItem) => void;
  handleNewConversation: () => Promise<void>;

  // Rename
  renamingId: string | null;
  renameValue: string;
  setRenameValue: (v: string) => void;
  startRename: (item: ConversationItem) => void;
  commitRename: (item: ConversationItem) => Promise<void>;
  cancelRename: () => void;

  // Delete
  deleteTarget: ConversationItem | null;
  isDeleting: boolean;
  setDeleteTarget: (item: ConversationItem | null) => void;
  confirmDelete: () => Promise<void>;

  // Duplicate
  duplicateModal: DuplicateModalState | null;
  setDuplicateModal: Dispatch<SetStateAction<DuplicateModalState | null>>;
  handleDuplicate: (id: string, name: string, desc: string) => Promise<void>;
  startDuplicate: (strategy: StrategyListItem) => void;

  // Saved toggle
  handleToggleSaved: (si: StrategyListItem) => Promise<void>;
}

export function useConversationSidebarActions({
  siteId,
  reportError,
  handlePlanError,
  refreshPlans,
  refreshStrategies,
  setPlanItems,
  setStrategyItems,
}: UseConversationSidebarActionsArgs): ConversationSidebarActions {
  // --- Store selectors ---
  const planSessionId = useSessionStore((s) => s.planSessionId);
  const setPlanSessionId = useSessionStore((s) => s.setPlanSessionId);
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyId = useSessionStore((s) => s.setStrategyId);
  const bumpPlanListVersion = useSessionStore((s) => s.bumpPlanListVersion);

  const removeStrategy = useStrategyListStore((s) => s.removeStrategy);

  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const clearStrategy = useStrategyStore((s) => s.clear);

  // --- Local state ---
  const [deleteTarget, setDeleteTarget] = useState<ConversationItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [duplicateModal, setDuplicateModal] = useState<DuplicateModalState | null>(
    null,
  );
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  // --- Derived ---
  const activeId = strategyId || planSessionId || null;

  // --- Selection ---
  const handleSelect = useCallback(
    (item: ConversationItem) => {
      if (item.kind === "plan") {
        setStrategyId(null);
        clearStrategy();
        setPlanSessionId(item.id);
      } else {
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

  // --- New conversation ---
  const handleNewConversation = useCallback(async () => {
    try {
      const res = await openStrategy({ siteId });
      clearStrategy();
      setPlanSessionId(null);
      setStrategyId(res.strategyId);
      // Hydrate the strategy so the sidebar can display it immediately.
      const now = new Date().toISOString();
      setStrategyItems((prev) => [
        {
          id: res.strategyId,
          name: "New Conversation",
          updatedAt: now,
          siteId,
          isSaved: false,
        },
        ...prev.filter((s) => s.id !== res.strategyId),
      ]);
      void refreshStrategies();
    } catch (error) {
      reportError(
        typeof error === "string" ? error : "Failed to start a new conversation.",
      );
    }
  }, [
    siteId,
    setStrategyId,
    clearStrategy,
    setPlanSessionId,
    setStrategyItems,
    refreshStrategies,
    reportError,
  ]);

  // --- Delete ---
  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      if (deleteTarget.kind === "plan") {
        // Legacy plan session: delete and clear if active.
        await deletePlanSession(deleteTarget.id).catch((error) => {
          handlePlanError(error, "Failed to delete conversation.");
        });
        if (planSessionId === deleteTarget.id) setPlanSessionId(null);
        await refreshPlans();
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
    handlePlanError,
    setPlanSessionId,
    setStrategyId,
    clearStrategy,
    removeStrategy,
    setStrategyItems,
    refreshPlans,
    refreshStrategies,
    reportError,
  ]);

  // --- Rename ---
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

  const cancelRename = useCallback(() => setRenamingId(null), []);

  // --- Duplicate ---
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

  const startDuplicate = useCallback((strategy: StrategyListItem) => {
    setDuplicateModal(initDuplicateModal(strategy));
    getStrategy(strategy.id)
      .then((loadedStrategy) => {
        setDuplicateModal((prev) =>
          prev ? applyDuplicateLoadSuccess(prev, loadedStrategy) : prev,
        );
      })
      .catch((err) => {
        console.error("[startDuplicate]", err);
        setDuplicateModal((prev) => (prev ? applyDuplicateLoadFailure(prev) : prev));
      });
  }, []);

  // --- Saved toggle ---
  const handleToggleSaved = useCallback(
    async (si: StrategyListItem) => {
      const nextSaved = !si.isSaved;
      try {
        await updateStrategyApi(si.id, { isSaved: nextSaved });
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
    [reportError, setStrategyItems],
  );

  return {
    activeId,
    handleSelect,
    handleNewConversation,
    renamingId,
    renameValue,
    setRenameValue,
    startRename,
    commitRename,
    cancelRename,
    deleteTarget,
    isDeleting,
    setDeleteTarget,
    confirmDelete,
    duplicateModal,
    setDuplicateModal,
    handleDuplicate,
    startDuplicate,
    handleToggleSaved,
  };
}
