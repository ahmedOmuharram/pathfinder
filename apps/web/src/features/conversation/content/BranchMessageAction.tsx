"use client";

import { useAuiState } from "@assistant-ui/react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GitBranch } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { MessageAction } from "@/components/ai-elements/message";
import { forkConversation } from "@/lib/api/conversations";

export function BranchMessageAction() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useParams<{ siteId?: string; conversationId?: string }>();
  const messageId = useAuiState((s) => s.message.id);

  const mutation = useMutation({
    mutationFn: async () => {
      const conversationId = params.conversationId;
      const siteId = params.siteId;
      if (conversationId == null || conversationId === "" || siteId == null || siteId === "") {
        throw new Error("Missing conversation or site context");
      }
      return forkConversation(conversationId, messageId);
    },
    onSuccess: (fork) => {
      void queryClient.invalidateQueries({
        queryKey: ["conversations", "list", params.siteId],
      });
      router.push(`/${params.siteId}/conversation/${fork.id}`);
    },
    onError: (err) => {
      toast.error(
        err instanceof Error
          ? err.message
          : "Failed to branch this conversation",
      );
    },
  });

  return (
    <MessageAction
      tooltip="Branch to a new chat from here"
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
    >
      <GitBranch />
    </MessageAction>
  );
}
