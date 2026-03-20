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
  deleteStrategy,
  getStrategy,
  openStrategy,
  restoreStrategy,
  updateStrategy as updateStrategyApi,
} from "@/lib/api/strategies";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useSettingsStore } from "@/state/useSettingsStore";
import { useStrategyStore } from "@/state/strategy/store";
import type { Strategy } from "@pathfinder/shared";
import { buildDuplicatePlan } from "@/features/sidebar/utils/duplicatePlan";
import {
  type DuplicateModalState,
  applyDuplicateLoadFailure,
  applyDuplicateLoadSuccess,
  initDuplicateModal,
} from "@/features/sidebar/utils/duplicateModalState";
import { runDeleteStrategyWorkflow } from "@/features/sidebar/services/strategySidebarWorkflows";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { DEFAULT_STREAM_NAME } from "@pathfinder/shared";

interface UseConversationSidebarActionsArgs {
  siteId: string;
  reportError: (message: string) => void;
  /** Lightweight re-fetch from local DB only (no WDK sync). */
  refetchStrategies: () => Promise<void>;
  setStrategyItems: Dispatch<SetStateAction<Strategy[]>>;
  setDismissedItems: Dispatch<SetStateAction<Strategy[]>>;
  /** Mark a strategy ID as recently deleted to prevent stale refetch re-adds. */
  markAsDeleted: (id: string) => void;
  setNewConversationInFlight: (inFlight: boolean) => void;
}

interface ConversationSidebarActions {
  /** Currently active conversation ID (strategy). */
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
  startDuplicate: (strategy: Strategy) => void;

  // Saved toggle
  handleToggleSaved: (si: Strategy) => Promise<void>;

  // Restore dismissed
  handleRestore: (strategyId: string) => Promise<void>;

  // Permanent delete (dismissed → hard-delete from PathFinder + WDK)
  permanentDeleteTarget: string | null;
  setPermanentDeleteTarget: (id: string | null) => void;
  confirmPermanentDelete: () => Promise<void>;
}

export function useConversationSidebarActions({
  siteId,
  reportError,
  refetchStrategies,
  setStrategyItems,
  setDismissedItems,
  markAsDeleted,
  setNewConversationInFlight,
}: UseConversationSidebarActionsArgs): ConversationSidebarActions {
  // --- Store selectors ---
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyId = useSessionStore((s) => s.setStrategyId);

  const deleteFromWdk = useSettingsStore((s) => s.deleteFromWdk);

  const removeStrategy = useStrategyStore((s) => s.removeStrategyFromList);

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
  const [permanentDeleteTarget, setPermanentDeleteTarget] = useState<string | null>(
    null,
  );

  // --- Derived ---
  const activeId = strategyId ?? null;

  // --- Selection ---
  const handleSelect = useCallback(
    (item: ConversationItem) => {
      const si = item.strategyItem;
      if (!si) return;
      setStrategyId(si.id);
      clearStrategy();
      getStrategy(si.id)
        .then((full) => {
          setStrategy(full);
          setStrategyMeta({
            name: full.name,
            recordType: full.recordType,
            siteId: full.siteId,
          });
        })
        .catch((err) => {
          setStrategyId(null);
          reportError(toUserMessage(err, "Couldn't load strategy. Refreshing list."));
          void refetchStrategies();
        });
    },
    [
      clearStrategy,
      setStrategyId,
      setStrategy,
      setStrategyMeta,
      reportError,
      refetchStrategies,
    ],
  );

  // --- New conversation ---
  const handleNewConversation = useCallback(async () => {
    // Signal that a new conversation is being created — prevents
    // ensureActiveConversation from auto-picking an old strategy
    // while the POST is in flight.
    setNewConversationInFlight(true);
    try {
      const res = await openStrategy({ siteId });
      clearStrategy();
      setStrategyId(res.strategyId);
      // Hydrate the strategy so the sidebar can display it immediately.
      const now = new Date().toISOString();
      setStrategyItems((prev) => [
        {
          id: res.strategyId,
          name: DEFAULT_STREAM_NAME,
          updatedAt: now,
          createdAt: now,
          siteId,
          recordType: null,
          steps: [],
          rootStepId: null,
          stepCount: 0,
          isSaved: false,
        },
        ...prev.filter((s) => s.id !== res.strategyId),
      ]);
      void refetchStrategies();
    } catch (error) {
      reportError(
        typeof error === "string" ? error : "Failed to start a new conversation.",
      );
    } finally {
      setNewConversationInFlight(false);
    }
  }, [
    siteId,
    setStrategyId,
    clearStrategy,
    setStrategyItems,
    setNewConversationInFlight,
    refetchStrategies,
    reportError,
  ]);

  // --- Delete ---
  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      const si = deleteTarget.strategyItem;
      if (si) {
        // Mark as deleted so stale refetch responses don't re-add it.
        markAsDeleted(si.id);
        await runDeleteStrategyWorkflow({
          item: si,
          currentStrategyId: strategyId ?? null,
          setStrategyItems,
          setDismissedItems,
          clearStrategy,
          removeStrategy,
          setStrategyId,
          setDeleteError: () => {},
          deleteStrategyApi: deleteStrategy,
          deleteFromWdk,
          refetchStrategies: () => {
            void refetchStrategies();
          },
          reportError: (msg) => reportError(msg),
        });
      }
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  }, [
    deleteTarget,
    strategyId,
    deleteFromWdk,
    setStrategyId,
    clearStrategy,
    removeStrategy,
    setStrategyItems,
    setDismissedItems,
    markAsDeleted,
    refetchStrategies,
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
        await updateStrategyApi(item.id, { name: next });
        void refetchStrategies();
      } catch (err) {
        reportError(toUserMessage(err, "Failed to rename."));
      }
      setRenamingId(null);
    },
    [renameValue, refetchStrategies, reportError],
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
      void refetchStrategies();
    },
    [refetchStrategies],
  );

  const startDuplicate = useCallback((strategy: Strategy) => {
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
    async (si: Strategy) => {
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

  // --- Restore dismissed ---
  const handleRestore = useCallback(
    async (strategyIdToRestore: string) => {
      try {
        const restored = await restoreStrategy(strategyIdToRestore);
        // Direct state update after the API confirms success.
        // Move the item from dismissed → active using the API response data
        // so the UI reflects the change immediately.  A background refetch
        // (fire-and-forget) is unreliable because the syncInFlight guard may
        // silently drop it, so the direct update is the primary mechanism.
        setDismissedItems((prev) => prev.filter((s) => s.id !== strategyIdToRestore));
        setStrategyItems((prev) => [
          restored,
          ...prev.filter((s) => s.id !== restored.id),
        ]);
      } catch (err) {
        reportError(toUserMessage(err, "Failed to restore strategy."));
      }
    },
    [reportError, setDismissedItems, setStrategyItems],
  );

  // --- Permanent delete (dismissed strategy → hard-delete from WDK) ---
  const confirmPermanentDelete = useCallback(async () => {
    if (permanentDeleteTarget == null) return;
    try {
      await deleteStrategy(permanentDeleteTarget, true);
      setDismissedItems((prev) => prev.filter((s) => s.id !== permanentDeleteTarget));
    } catch (err) {
      reportError(toUserMessage(err, "Failed to permanently delete strategy."));
    } finally {
      setPermanentDeleteTarget(null);
    }
  }, [permanentDeleteTarget, setDismissedItems, reportError]);

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
    handleRestore,
    permanentDeleteTarget,
    setPermanentDeleteTarget,
    confirmPermanentDelete,
  };
}
