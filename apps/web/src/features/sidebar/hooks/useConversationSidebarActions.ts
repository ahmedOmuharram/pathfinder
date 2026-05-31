"use client";

import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";

import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import {
  useDeleteWorkflow,
  type DeleteWorkflow,
} from "@/features/sidebar/hooks/useDeleteWorkflow";
import {
  useRenameWorkflow,
  type RenameWorkflow,
} from "@/features/sidebar/hooks/useRenameWorkflow";
import type { ConversationResponse } from "@pathfinder/shared/generated/types/ConversationResponse";
import { listStrategiesQueryOptions } from "@pathfinder/shared/generated/hooks/useListStrategies";
import { updateStrategy } from "@pathfinder/shared/generated/hooks/useUpdateStrategy";
import { toUserMessage } from "@/lib/api/errors";

interface UseConversationSidebarActionsArgs {
  siteId: string;
  reportError: (message: string) => void;
}

interface ConversationSidebarActions extends RenameWorkflow, DeleteWorkflow {
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
  const pathname = usePathname();
  const activeId = pathname.match(/\/conversation\/([^/?#]+)/)?.[1] ?? null;

  const rename = useRenameWorkflow({ siteId, reportError });
  const deleteWorkflow = useDeleteWorkflow({
    siteId,
    reportError,
    activeChatId: activeId,
  });

  const listKey = listStrategiesQueryOptions({ siteId }).queryKey;

  const handleNewConversation = async (): Promise<void> => {
    router.push(`/${siteId}/conversation`);
  };

  const handleToggleSaved = async (item: ConversationItem): Promise<void> => {
    const nextSaved = !item.isSaved;
    try {
      const updated = await updateStrategy(item.id, { isSaved: nextSaved });
      queryClient.setQueryData<ConversationResponse[]>(listKey, (old) =>
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
  };
}
