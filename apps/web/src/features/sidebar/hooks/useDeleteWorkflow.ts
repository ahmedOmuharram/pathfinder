"use client";

/**
 * Delete / restore / permanent-delete workflows for the conversation sidebar.
 *
 * Owns delete-confirmation modal state (soft-delete), permanent-delete
 * confirmation (hard-delete from WDK), and the restore-from-dismissed flow.
 */

import { type Dispatch, type SetStateAction, useCallback, useState } from "react";
import { deleteStrategy, restoreStrategy } from "@/lib/api/strategies";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useSettingsStore } from "@/state/useSettingsStore";
import { useStrategyStore } from "@/state/strategy/store";
import type { Strategy } from "@pathfinder/shared";
import { runDeleteStrategyWorkflow } from "@/features/sidebar/services/strategySidebarWorkflows";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

interface UseDeleteWorkflowArgs {
  reportError: (message: string) => void;
  refetchStrategies: () => Promise<void>;
  setStrategyItems: Dispatch<SetStateAction<Strategy[]>>;
  setDismissedItems: Dispatch<SetStateAction<Strategy[]>>;
  markAsDeleted: (id: string) => void;
}

export interface DeleteWorkflow {
  // Soft-delete
  deleteTarget: ConversationItem | null;
  isDeleting: boolean;
  setDeleteTarget: (item: ConversationItem | null) => void;
  confirmDelete: () => Promise<void>;

  // Restore dismissed
  handleRestore: (strategyId: string) => Promise<void>;

  // Permanent delete (dismissed -> hard-delete from PathFinder + WDK)
  permanentDeleteTarget: string | null;
  setPermanentDeleteTarget: (id: string | null) => void;
  confirmPermanentDelete: () => Promise<void>;
}

export function useDeleteWorkflow({
  reportError,
  refetchStrategies,
  setStrategyItems,
  setDismissedItems,
  markAsDeleted,
}: UseDeleteWorkflowArgs): DeleteWorkflow {
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyId = useSessionStore((s) => s.setStrategyId);
  const deleteFromWdk = useSettingsStore((s) => s.deleteFromWdk);
  const removeStrategy = useStrategyStore((s) => s.removeStrategyFromList);
  const clearStrategy = useStrategyStore((s) => s.clear);

  const [deleteTarget, setDeleteTarget] = useState<ConversationItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [permanentDeleteTarget, setPermanentDeleteTarget] = useState<string | null>(
    null,
  );

  // --- Soft-delete ---
  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      const si = deleteTarget.strategyItem;
      if (si) {
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

  // --- Restore dismissed ---
  const handleRestore = useCallback(
    async (strategyIdToRestore: string) => {
      try {
        const restored = await restoreStrategy(strategyIdToRestore);
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

  // --- Permanent delete (dismissed strategy -> hard-delete from WDK) ---
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
    deleteTarget,
    isDeleting,
    setDeleteTarget,
    confirmDelete,
    handleRestore,
    permanentDeleteTarget,
    setPermanentDeleteTarget,
    confirmPermanentDelete,
  };
}
