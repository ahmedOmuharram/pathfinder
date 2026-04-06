"use client";

/**
 * Rename workflow for the conversation sidebar.
 *
 * Owns inline-rename UI state (which item is being renamed, the
 * current rename value) and commits renames to the API.
 */

import { useCallback, useState } from "react";
import { updateStrategy as updateStrategyApi } from "@/lib/api/strategies";
import { toUserMessage } from "@/lib/api/errors";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

interface UseRenameWorkflowArgs {
  reportError: (message: string) => void;
  refetchStrategies: () => Promise<void>;
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
  reportError,
  refetchStrategies,
}: UseRenameWorkflowArgs): RenameWorkflow {
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
        void refetchStrategies();
      } catch (err) {
        reportError(toUserMessage(err, "Failed to rename."));
      }
      setRenamingId(null);
    },
    [renameValue, refetchStrategies, reportError],
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
