"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { conversationDetailKey, deleteConversation } from "@/lib/api/conversations";
import { toUserMessage } from "@/lib/api/errors";

export interface DeleteStrategyVars {
  conversationId: string;
  siteId: string;
}

export function useDeleteStrategyMutation() {
  const router = useRouter();
  const queryClient = useQueryClient();
  return useMutation<void, Error, DeleteStrategyVars>({
    mutationFn: async ({ conversationId }) => {
      await deleteConversation(conversationId);
    },
    onSuccess: (_data, { siteId, conversationId }) => {
      queryClient.removeQueries({ queryKey: conversationDetailKey(conversationId) });
      router.push(`/${siteId}/conversation`);
      toast.success("Strategy deleted");
    },
    onError: (err) => {
      toast.error(toUserMessage(err, "Failed to delete strategy"));
    },
  });
}
