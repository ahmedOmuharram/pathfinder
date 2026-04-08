"use client";

/**
 * Delete / restore / permanent-delete workflows for the conversation sidebar.
 *
 * Owns delete-confirmation modal state (soft-delete), permanent-delete
 * confirmation (hard-delete from WDK), and the restore-from-dismissed flow.
 *
 * Uses useQueryClient() directly for optimistic cache updates.
 */

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { deleteStrategy, restoreStrategy, strategiesListOptions, dismissedStrategiesOptions } from "@/lib/api/strategies";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useSettingsStore } from "@/state/useSettingsStore";
import { useStrategyStore } from "@/state/strategy/store";
import type { Strategy } from "@pathfinder/shared";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

interface UseDeleteWorkflowArgs {
  siteId: string;
  reportError: (message: string) => void;
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
  siteId,
  reportError,
}: UseDeleteWorkflowArgs): DeleteWorkflow {
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyId = useSessionStore((s) => s.setStrategyId);
  const deleteFromWdk = useSettingsStore((s) => s.deleteFromWdk);
  const clearStrategy = useStrategyStore((s) => s.clear);
  const queryClient = useQueryClient();

  const [deleteTarget, setDeleteTarget] = useState<ConversationItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [permanentDeleteTarget, setPermanentDeleteTarget] = useState<string | null>(
    null,
  );

  const listKey = strategiesListOptions(siteId).queryKey;
  const dismissedKey = dismissedStrategiesOptions(siteId).queryKey;

  // --- Soft-delete ---
  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      const si = deleteTarget.strategyItem;
      if (si) {
        // Optimistic: remove from main list.
        queryClient.setQueryData<Strategy[]>(listKey, (old) =>
          (old ?? []).filter((entry) => entry.id !== si.id),
        );

        // For WDK-linked strategies that will be soft-deleted (dismissed),
        // optimistically add to the dismissed list.
        const willSoftDelete = si.wdkStrategyId != null && !deleteFromWdk;
        if (willSoftDelete) {
          queryClient.setQueryData<Strategy[]>(dismissedKey, (old) => [
            ...(old ?? []),
            si,
          ]);
        }

        // If deleting active strategy, reset active state.
        if (strategyId === si.id) {
          clearStrategy();
          setStrategyId(null);
        }

        try {
          await deleteStrategy(si.id, deleteFromWdk);
        } catch (e) {
          // Rollback optimistic dismissed addition on failure.
          if (willSoftDelete) {
            queryClient.setQueryData<Strategy[]>(dismissedKey, (old) =>
              (old ?? []).filter((s) => s.id !== si.id),
            );
          }
          reportError(
            toUserMessage(e, "Failed to delete strategy. Please try again."),
          );
        } finally {
          void queryClient.invalidateQueries({ queryKey: listKey });
          void queryClient.invalidateQueries({ queryKey: dismissedKey });
        }
      }
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  };

  // --- Restore dismissed ---
  const handleRestore = async (strategyIdToRestore: string) => {
      try {
        const restored = await restoreStrategy(strategyIdToRestore);
        queryClient.setQueryData<Strategy[]>(dismissedKey, (old) =>
          (old ?? []).filter((s) => s.id !== strategyIdToRestore),
        );
        queryClient.setQueryData<Strategy[]>(listKey, (old) => [
          restored,
          ...(old ?? []).filter((s) => s.id !== restored.id),
        ]);
      } catch (err) {
        reportError(toUserMessage(err, "Failed to restore strategy."));
      } finally {
        void queryClient.invalidateQueries({ queryKey: listKey });
        void queryClient.invalidateQueries({ queryKey: dismissedKey });
    }
  };

  // --- Permanent delete (dismissed strategy -> hard-delete from WDK) ---
  const confirmPermanentDelete = async () => {
    if (permanentDeleteTarget == null) return;
    try {
      await deleteStrategy(permanentDeleteTarget, true);
      queryClient.setQueryData<Strategy[]>(dismissedKey, (old) =>
        (old ?? []).filter((s) => s.id !== permanentDeleteTarget),
      );
    } catch (err) {
      reportError(toUserMessage(err, "Failed to permanently delete strategy."));
    } finally {
      void queryClient.invalidateQueries({ queryKey: dismissedKey });
      setPermanentDeleteTarget(null);
    }
  };

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
