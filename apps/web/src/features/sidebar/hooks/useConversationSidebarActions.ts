"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";

import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import {
  useDeleteWorkflow,
  type DeleteWorkflow,
} from "@/features/sidebar/hooks/useDeleteWorkflow";
import {
  useDuplicateWorkflow,
  type DuplicateWorkflow,
} from "@/features/sidebar/hooks/useDuplicateWorkflow";
import {
  useRenameWorkflow,
  type RenameWorkflow,
} from "@/features/sidebar/hooks/useRenameWorkflow";
import {
  chatListOptions,
  setChatSaved,
  type ChatListItem,
} from "@/lib/api/chats";
import { toUserMessage } from "@/lib/api/errors";

interface UseConversationSidebarActionsArgs {
  siteId: string;
  reportError: (message: string) => void;
}

interface ConversationSidebarActions
  extends RenameWorkflow,
    DuplicateWorkflow,
    DeleteWorkflow {
  activeId: string | null;
  handleSelect: (item: ConversationItem) => void;
  handleNewConversation: () => Promise<void>;
  handleToggleSaved: (item: ConversationItem) => Promise<void>;
}

export function useConversationSidebarActions({
  siteId,
  reportError,
}: UseConversationSidebarActionsArgs): ConversationSidebarActions {
  const queryClient = useQueryClient();
  const router = useRouter();
  const params = useParams<{ convoId?: string }>();
  const activeId = params.convoId ?? null;

  const rename = useRenameWorkflow({ siteId, reportError });
  const duplicate = useDuplicateWorkflow({ siteId, reportError });
  const deleteWorkflow = useDeleteWorkflow({
    siteId,
    reportError,
    activeChatId: activeId,
  });

  const listKey = chatListOptions(siteId).queryKey;

  const handleSelect = (item: ConversationItem) => {
    router.push(`/chat/${item.id}`);
  };

  const handleNewConversation = async (): Promise<void> => {
    router.push("/chat");
  };

  const handleToggleSaved = async (item: ConversationItem): Promise<void> => {
    const nextSaved = !item.isSaved;
    try {
      const updated = await setChatSaved(item.id, nextSaved);
      queryClient.setQueryData<ChatListItem[]>(listKey, (old) =>
        (old ?? []).map((c) => (c.id === item.id ? updated : c)),
      );
    } catch (err) {
      reportError(
        toUserMessage(
          err,
          nextSaved
            ? "Failed to mark conversation as saved."
            : "Failed to unmark saved.",
        ),
      );
    }
  };

  return {
    activeId,
    handleSelect,
    handleNewConversation,
    handleToggleSaved,
    ...rename,
    ...deleteWorkflow,
    ...duplicate,
  };
}
