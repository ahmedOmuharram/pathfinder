"use client";

/**
 * Action handlers and modal state for the conversation sidebar.
 *
 * Composes sub-hooks for rename, delete, and duplicate workflows,
 * and owns selection, new-conversation, and saved-toggle handlers.
 *
 * All cache operations use useQueryClient() directly — no shim props.
 */

import { useQueryClient } from "@tanstack/react-query";
import { getStrategy, openStrategy, updateStrategy as updateStrategyApi, strategiesListOptions, dismissedStrategiesOptions } from "@/lib/api/strategies";
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
  setNewConversationInFlight,
}: UseConversationSidebarActionsArgs): ConversationSidebarActions {
  // --- Store selectors ---
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyId = useSessionStore((s) => s.setStrategyId);

  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const clearStrategy = useStrategyStore((s) => s.clear);

  const queryClient = useQueryClient();

  // --- Derived ---
  const activeId = strategyId ?? null;

  const listKey = strategiesListOptions(siteId).queryKey;
  const dismissedKey = dismissedStrategiesOptions(siteId).queryKey;

  // --- Sub-hooks ---
  const rename = useRenameWorkflow({ siteId, reportError });
  const duplicate = useDuplicateWorkflow({ siteId });
  const deleteWorkflow = useDeleteWorkflow({ siteId, reportError });

  // --- Selection ---
  const handleSelect = (item: ConversationItem) => {
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
          void queryClient.invalidateQueries({ queryKey: listKey });
          void queryClient.invalidateQueries({ queryKey: dismissedKey });
        });
  };

  // --- New conversation ---
  const handleNewConversation = async () => {
    setNewConversationInFlight(true);
    try {
      const res = await openStrategy({ siteId });
      clearStrategy();
      setStrategyId(res.strategyId);
      const now = new Date().toISOString();
      queryClient.setQueryData<Strategy[]>(listKey, (old) => [
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
        ...(old ?? []).filter((s) => s.id !== res.strategyId),
      ]);
      void queryClient.invalidateQueries({ queryKey: listKey });
      void queryClient.invalidateQueries({ queryKey: dismissedKey });
    } catch (error) {
      reportError(
        typeof error === "string" ? error : "Failed to start a new conversation.",
      );
    } finally {
      setNewConversationInFlight(false);
    }
  };

  // --- Saved toggle ---
  const handleToggleSaved = async (si: Strategy) => {
    const nextSaved = !si.isSaved;
    try {
      await updateStrategyApi(si.id, { isSaved: nextSaved });
      queryClient.setQueryData<Strategy[]>(listKey, (old) =>
        (old ?? []).map((item) =>
          item.id === si.id ? { ...item, isSaved: nextSaved } : item,
        ),
      );
      void queryClient.invalidateQueries({ queryKey: listKey });
    } catch (err) {
      reportError(
        toUserMessage(
          err,
          nextSaved ? "Failed to save strategy." : "Failed to revert to draft.",
        ),
      );
    }
  };

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
