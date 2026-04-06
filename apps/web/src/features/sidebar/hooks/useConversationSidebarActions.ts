"use client";

/**
 * Action handlers and modal state for the conversation sidebar.
 *
 * Composes sub-hooks for rename, delete, and duplicate workflows,
 * and owns selection, new-conversation, and saved-toggle handlers.
 */

import { type Dispatch, type SetStateAction, useCallback } from "react";
import { getStrategy, openStrategy, updateStrategy as updateStrategyApi } from "@/lib/api/strategies";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";
import type { Strategy } from "@pathfinder/shared";
import { DEFAULT_STREAM_NAME } from "@pathfinder/shared";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import { useRenameWorkflow, type RenameWorkflow } from "@/features/sidebar/hooks/useRenameWorkflow";
import { useDuplicateWorkflow, type DuplicateWorkflow } from "@/features/sidebar/hooks/useDuplicateWorkflow";
import { useDeleteWorkflow, type DeleteWorkflow } from "@/features/sidebar/hooks/useDeleteWorkflow";

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

interface ConversationSidebarActions extends RenameWorkflow, DuplicateWorkflow, DeleteWorkflow {
  /** Currently active conversation ID (strategy). */
  activeId: string | null;

  // Selection
  handleSelect: (item: ConversationItem) => void;
  handleNewConversation: () => Promise<void>;

  // Saved toggle
  handleToggleSaved: (si: Strategy) => Promise<void>;
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

  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const clearStrategy = useStrategyStore((s) => s.clear);

  // --- Derived ---
  const activeId = strategyId ?? null;

  // --- Sub-hooks ---
  const rename = useRenameWorkflow({ reportError, refetchStrategies });
  const duplicate = useDuplicateWorkflow({ refetchStrategies });
  const deleteWorkflow = useDeleteWorkflow({
    reportError,
    refetchStrategies,
    setStrategyItems,
    setDismissedItems,
    markAsDeleted,
  });

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
    setNewConversationInFlight(true);
    try {
      const res = await openStrategy({ siteId });
      clearStrategy();
      setStrategyId(res.strategyId);
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

  return {
    activeId,
    handleSelect,
    handleNewConversation,
    ...rename,
    ...deleteWorkflow,
    ...duplicate,
    handleToggleSaved,
  };
}
