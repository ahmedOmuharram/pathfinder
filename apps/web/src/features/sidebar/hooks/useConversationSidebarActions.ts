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
  conversationListOptions,
  setConversationSaved,
  type ConversationSummary,
} from "@/lib/api/conversations";
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
  handleNewConversation: () => Promise<void>;
  handleToggleSaved: (item: ConversationItem) => Promise<void>;
}

export function useConversationSidebarActions({
  siteId,
  reportError,
}: UseConversationSidebarActionsArgs): ConversationSidebarActions {
  const queryClient = useQueryClient();
  const router = useRouter();
  const params = useParams<{ conversationId?: string }>();
  const activeId = params.conversationId ?? null;

  const rename = useRenameWorkflow({ siteId, reportError });
  const duplicate = useDuplicateWorkflow({ siteId, reportError });
  const deleteWorkflow = useDeleteWorkflow({
    siteId,
    reportError,
    activeChatId: activeId,
  });

  const listKey = conversationListOptions(siteId).queryKey;

  const handleNewConversation = async (): Promise<void> => {
    router.push("/conversation");
  };

  const handleToggleSaved = async (item: ConversationItem): Promise<void> => {
    const nextSaved = !item.isSaved;
    try {
      const updated = await setConversationSaved(item.id, nextSaved);
      queryClient.setQueryData<ConversationSummary[]>(listKey, (old) =>
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
    handleNewConversation,
    handleToggleSaved,
    ...rename,
    ...deleteWorkflow,
    ...duplicate,
  };
}
