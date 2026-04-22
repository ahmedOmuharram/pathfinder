"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { deleteConversation } from "@/lib/api/conversations";
import { toUserMessage } from "@/lib/api/errors";
import { useStrategyStore } from "@/state/strategy/store";

export interface DeleteStrategyVars {
  conversationId: string;
  siteId: string;
}

/**
 * Delete the strategy (and its conversation) on the server, clear local store,
 * navigate to the conversation list, toast on success.
 */
export function useDeleteStrategyMutation() {
  const router = useRouter();
  return useMutation<void, Error, DeleteStrategyVars>({
    mutationFn: async ({ conversationId }) => {
      await deleteConversation(conversationId);
    },
    onSuccess: (_data, { siteId }) => {
      useStrategyStore.getState().setStrategy(null);
      router.push(`/${siteId}/conversation`);
      toast.success("Strategy deleted");
    },
    onError: (err) => {
      toast.error(toUserMessage(err, "Failed to delete strategy"));
    },
  });
}
