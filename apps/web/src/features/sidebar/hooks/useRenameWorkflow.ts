"use client";

/**
 * Rename workflow for the conversation sidebar.
 *
 * Owns inline-rename UI state (which item is being renamed, the
 * current rename value) and commits renames to the API.
 *
 * Uses useQueryClient() directly for cache invalidation after rename.
 */

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { updateStrategy as updateStrategyApi, strategiesListOptions, dismissedStrategiesOptions } from "@/lib/api/strategies";
import { toUserMessage } from "@/lib/api/errors";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

interface UseRenameWorkflowArgs {
  siteId: string;
  reportError: (message: string) => void;
}

export interface RenameWorkflow {
  renamingId: string | null;
  renameValue: string;
  setRenameValue: (v: string) => void;
  startRename: (item: ConversationItem) => void;
  commitRename: (item: ConversationItem) => Promise<void>;
  cancelRename: () => void;
}

export function useRenameWorkflow({
  siteId,
  reportError,
}: UseRenameWorkflowArgs): RenameWorkflow {
  const queryClient = useQueryClient();
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

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
        void queryClient.invalidateQueries({ queryKey: strategiesListOptions(siteId).queryKey });
        void queryClient.invalidateQueries({ queryKey: dismissedStrategiesOptions(siteId).queryKey });
      } catch (err) {
        reportError(toUserMessage(err, "Failed to rename."));
      }
      setRenamingId(null);
    },
    [renameValue, queryClient, siteId, reportError],
  );

  const cancelRename = useCallback(() => setRenamingId(null), []);

  return {
    renamingId,
    renameValue,
    setRenameValue,
    startRename,
    commitRename,
    cancelRename,
  };
}
