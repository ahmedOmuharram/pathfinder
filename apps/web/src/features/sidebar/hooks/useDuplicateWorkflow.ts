"use client";

/**
 * Duplicate workflow for the conversation sidebar.
 *
 * Clones a conversation (new row + copied messages) via the chats API
 * and routes the user to the fresh copy.
 */

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import {
  chatListOptions,
  dismissedChatsOptions,
  duplicateChat,
} from "@/lib/api/chats";
import { toUserMessage } from "@/lib/api/errors";

interface UseDuplicateWorkflowArgs {
  siteId: string;
  reportError: (message: string) => void;
}

export interface DuplicateWorkflow {
  duplicateTarget: ConversationItem | null;
  isDuplicating: boolean;
  setDuplicateTarget: (item: ConversationItem | null) => void;
  confirmDuplicate: () => Promise<void>;
}

export function useDuplicateWorkflow({
  siteId,
  reportError,
}: UseDuplicateWorkflowArgs): DuplicateWorkflow {
  const queryClient = useQueryClient();
  const router = useRouter();

  const [duplicateTarget, setDuplicateTarget] =
    useState<ConversationItem | null>(null);
  const [isDuplicating, setIsDuplicating] = useState(false);

  const listKey = chatListOptions(siteId).queryKey;
  const dismissedKey = dismissedChatsOptions(siteId).queryKey;

  const confirmDuplicate = async () => {
    if (!duplicateTarget) return;
    setIsDuplicating(true);
    try {
      const { id: newId } = await duplicateChat(duplicateTarget.id);
      router.push(`/chat/${newId}`);
    } catch (err) {
      reportError(toUserMessage(err, "Failed to duplicate conversation."));
    } finally {
      void queryClient.invalidateQueries({ queryKey: listKey });
      void queryClient.invalidateQueries({ queryKey: dismissedKey });
      setIsDuplicating(false);
      setDuplicateTarget(null);
    }
  };

  return {
    duplicateTarget,
    isDuplicating,
    setDuplicateTarget,
    confirmDuplicate,
  };
}
