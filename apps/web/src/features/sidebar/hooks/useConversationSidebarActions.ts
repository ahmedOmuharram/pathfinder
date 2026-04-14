"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  dismissedStrategiesOptions,
  getStrategy,
  strategiesListOptions,
  updateStrategy as updateStrategyApi,
} from "@/lib/api/strategies";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";
import type { Strategy } from "@pathfinder/shared";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";
import {
  useRenameWorkflow,
  type RenameWorkflow,
} from "@/features/sidebar/hooks/useRenameWorkflow";
import {
  useDuplicateWorkflow,
  type DuplicateWorkflow,
} from "@/features/sidebar/hooks/useDuplicateWorkflow";
import {
  useDeleteWorkflow,
  type DeleteWorkflow,
} from "@/features/sidebar/hooks/useDeleteWorkflow";

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
  handleToggleSaved: (si: Strategy) => Promise<void>;
}

export function useConversationSidebarActions({
  siteId,
  reportError,
}: UseConversationSidebarActionsArgs): ConversationSidebarActions {
  const strategyId = useSessionStore((s) => s.strategyId);
  const setStrategyId = useSessionStore((s) => s.setStrategyId);
  const setStrategyMeta = useStrategyStore((s) => s.setStrategyMeta);
  const setStrategy = useStrategyStore((s) => s.setStrategy);
  const clearStrategy = useStrategyStore((s) => s.clear);

  const queryClient = useQueryClient();
  const router = useRouter();

  const activeId = strategyId ?? null;
  const listKey = strategiesListOptions(siteId).queryKey;
  const dismissedKey = dismissedStrategiesOptions(siteId).queryKey;

  const rename = useRenameWorkflow({ siteId, reportError });
  const duplicate = useDuplicateWorkflow({ siteId });
  const deleteWorkflow = useDeleteWorkflow({ siteId, reportError });

  const handleSelect = (item: ConversationItem) => {
    const si = item.strategyItem;
    if (!si) return;
    router.push(`/chat/${si.id}`);
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
        reportError(
          toUserMessage(err, "Couldn't load strategy. Refreshing list."),
        );
        void queryClient.invalidateQueries({ queryKey: listKey });
        void queryClient.invalidateQueries({ queryKey: dismissedKey });
      });
  };

  const handleNewConversation = async (): Promise<void> => {
    clearStrategy();
    setStrategyId(null);
    router.push("/chat");
  };

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
