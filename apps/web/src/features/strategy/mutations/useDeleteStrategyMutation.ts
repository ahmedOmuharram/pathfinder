"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { deleteStrategy } from "@pathfinder/shared/generated/hooks/useDeleteStrategy";
import { strategyQueryKey } from "@/lib/api/strategy";
import { toUserMessage } from "@/lib/api/errors";
import { chatRoot } from "@/lib/routes";

export interface DeleteStrategyVars {
  conversationId: string;
  siteId: string;
}

export function useDeleteStrategyMutation() {
  const router = useRouter();
  const queryClient = useQueryClient();
  return useMutation<void, Error, DeleteStrategyVars>({
    mutationFn: async ({ conversationId }) => {
      await deleteStrategy(conversationId);
    },
    onSuccess: (_data, { siteId, conversationId }) => {
      queryClient.removeQueries({ queryKey: strategyQueryKey(conversationId) });
      router.push(chatRoot(siteId));
      toast.success("Strategy deleted");
    },
    onError: (err) => {
      toast.error(toUserMessage(err, "Failed to delete strategy"));
    },
  });
}
