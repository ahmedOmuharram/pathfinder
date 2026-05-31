"use client";

/**
 * Delete / dismiss / restore workflows for the conversation sidebar.
 *
 * - Dismiss (soft-delete): hides the chat from the main list, shows it
 *   in the dismissed list.
 * - Restore: un-dismisses a previously-dismissed chat.
 * - Permanent delete: hard-deletes a dismissed chat (and its messages)
 *   from the backend.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import type { ConversationResponse } from "@pathfinder/shared/generated/types/ConversationResponse";
import { listStrategiesQueryOptions } from "@pathfinder/shared/generated/hooks/useListStrategies";
import { listDismissedStrategiesQueryOptions } from "@pathfinder/shared/generated/hooks/useListDismissedStrategies";
import { deleteStrategy } from "@pathfinder/shared/generated/hooks/useDeleteStrategy";
import { dismissConversation } from "@pathfinder/shared/generated/hooks/useDismissConversation";
import { restoreStrategy } from "@pathfinder/shared/generated/hooks/useRestoreStrategy";
import { toUserMessage } from "@/lib/api/errors";

interface UseDeleteWorkflowArgs {
  siteId: string;
  reportError: (message: string) => void;
  activeChatId: string | null;
}

export interface DeleteWorkflow {
  deleteTarget: ConversationItem | null;
  isDeleting: boolean;
  setDeleteTarget: (item: ConversationItem | null) => void;
  confirmDelete: (options?: { cascade?: boolean }) => Promise<void>;

  handleRestore: (conversationId: string) => Promise<void>;

  permanentDeleteTarget: string | null;
  setPermanentDeleteTarget: (id: string | null) => void;
  confirmPermanentDelete: (options?: { cascade?: boolean }) => Promise<void>;
}

export function useDeleteWorkflow({
  siteId,
  reportError,
  activeChatId,
}: UseDeleteWorkflowArgs): DeleteWorkflow {
  const queryClient = useQueryClient();
  const router = useRouter();

  const [deleteTarget, setDeleteTarget] = useState<ConversationItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [permanentDeleteTarget, setPermanentDeleteTarget] = useState<string | null>(
    null,
  );

  const listKey = listStrategiesQueryOptions({ siteId }).queryKey;
  const dismissedKey = listDismissedStrategiesQueryOptions({ siteId }).queryKey;

  const confirmDelete = async (options: { cascade?: boolean } = {}) => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      const target = deleteTarget;
      const isWdkLinked = target.chat.wdkStrategyId != null;
      if (isWdkLinked) {
        // Soft dismiss for WDK-linked chats so sync won't reimport them.
        queryClient.setQueryData<ConversationResponse[]>(listKey, (old) =>
          (old ?? []).filter((c) => c.id !== target.id),
        );
        queryClient.setQueryData<ConversationResponse[]>(dismissedKey, (old) => [
          target.chat,
          ...(old ?? []).filter((c) => c.id !== target.id),
        ]);
        if (activeChatId === target.id) {
          router.push(`/${siteId}/conversation`);
        }
        try {
          await dismissConversation(target.id);
        } catch (err) {
          queryClient.setQueryData<ConversationResponse[]>(listKey, (old) => [
            target.chat,
            ...(old ?? []).filter((c) => c.id !== target.id),
          ]);
          queryClient.setQueryData<ConversationResponse[]>(dismissedKey, (old) =>
            (old ?? []).filter((c) => c.id !== target.id),
          );
          reportError(toUserMessage(err, "Failed to dismiss conversation."));
        } finally {
          void queryClient.invalidateQueries({ queryKey: listKey });
          void queryClient.invalidateQueries({ queryKey: dismissedKey });
        }
        return;
      }
      // Non-WDK chat: hard-delete. With cascade=true, subtree goes; otherwise
      // direct children climb to this node's parent (repo handles it).
      if (activeChatId === target.id) {
        router.push(`/${siteId}/conversation`);
      }
      try {
        await deleteStrategy(
          target.id,
          options.cascade === true ? { cascade: true } : undefined,
        );
      } catch (err) {
        reportError(toUserMessage(err, "Failed to delete conversation."));
      } finally {
        void queryClient.invalidateQueries({ queryKey: listKey });
        void queryClient.invalidateQueries({ queryKey: dismissedKey });
      }
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  };

  const handleRestore = async (conversationId: string) => {
    try {
      await restoreStrategy(conversationId);
    } catch (err) {
      reportError(toUserMessage(err, "Failed to restore conversation."));
    } finally {
      void queryClient.invalidateQueries({ queryKey: listKey });
      void queryClient.invalidateQueries({ queryKey: dismissedKey });
    }
  };

  const confirmPermanentDelete = async (options: { cascade?: boolean } = {}) => {
    if (permanentDeleteTarget === null) return;
    const id = permanentDeleteTarget;
    try {
      await deleteStrategy(
        id,
        options.cascade === true ? { cascade: true } : undefined,
      );
      queryClient.setQueryData<ConversationResponse[]>(dismissedKey, (old) =>
        (old ?? []).filter((c) => c.id !== id),
      );
    } catch (err) {
      reportError(toUserMessage(err, "Failed to permanently delete conversation."));
    } finally {
      void queryClient.invalidateQueries({ queryKey: listKey });
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
