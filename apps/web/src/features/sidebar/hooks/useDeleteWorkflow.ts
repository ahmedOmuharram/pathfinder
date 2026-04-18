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
import {
  conversationListOptions,
  deleteConversation,
  dismissConversation,
  dismissedConversationsOptions,
  restoreConversation,
  type ConversationSummary,
} from "@/lib/api/conversations";
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
  confirmDelete: () => Promise<void>;

  handleRestore: (chatId: string) => Promise<void>;

  permanentDeleteTarget: string | null;
  setPermanentDeleteTarget: (id: string | null) => void;
  confirmPermanentDelete: () => Promise<void>;
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
  const [permanentDeleteTarget, setPermanentDeleteTarget] = useState<
    string | null
  >(null);

  const listKey = conversationListOptions(siteId).queryKey;
  const dismissedKey = dismissedConversationsOptions(siteId).queryKey;

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      const target = deleteTarget;
      // Optimistic: remove from active list, add to dismissed list.
      queryClient.setQueryData<ConversationSummary[]>(listKey, (old) =>
        (old ?? []).filter((c) => c.id !== target.id),
      );
      queryClient.setQueryData<ConversationSummary[]>(dismissedKey, (old) => [
        target.chat,
        ...(old ?? []).filter((c) => c.id !== target.id),
      ]);
      if (activeChatId === target.id) {
        router.push("/conversation");
      }
      try {
        await dismissConversation(target.id);
      } catch (err) {
        // Rollback: put back into active list, remove from dismissed.
        queryClient.setQueryData<ConversationSummary[]>(listKey, (old) => [
          target.chat,
          ...(old ?? []).filter((c) => c.id !== target.id),
        ]);
        queryClient.setQueryData<ConversationSummary[]>(dismissedKey, (old) =>
          (old ?? []).filter((c) => c.id !== target.id),
        );
        reportError(toUserMessage(err, "Failed to dismiss conversation."));
      } finally {
        void queryClient.invalidateQueries({ queryKey: listKey });
        void queryClient.invalidateQueries({ queryKey: dismissedKey });
      }
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  };

  const handleRestore = async (chatId: string) => {
    try {
      await restoreConversation(chatId);
    } catch (err) {
      reportError(toUserMessage(err, "Failed to restore conversation."));
    } finally {
      void queryClient.invalidateQueries({ queryKey: listKey });
      void queryClient.invalidateQueries({ queryKey: dismissedKey });
    }
  };

  const confirmPermanentDelete = async () => {
    if (permanentDeleteTarget === null) return;
    const id = permanentDeleteTarget;
    try {
      await deleteConversation(id);
      queryClient.setQueryData<ConversationSummary[]>(dismissedKey, (old) =>
        (old ?? []).filter((c) => c.id !== id),
      );
    } catch (err) {
      reportError(
        toUserMessage(err, "Failed to permanently delete conversation."),
      );
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
