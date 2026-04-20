"use client";

import { useAuiState } from "@assistant-ui/react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GitBranch } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { toast } from "sonner";

import { MessageAction } from "@/components/ai-elements/message";
import { forkConversation } from "@/lib/api/conversations";

const ROUTE_RE = /^\/([^/]+)\/conversation\/([^/?#]+)/;

export function BranchMessageAction() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const pathname = usePathname();
  const match = pathname.match(ROUTE_RE);
  const siteId = match?.[1] ?? null;
  const conversationId = match?.[2] ?? null;
  const messageId = useAuiState((s) => s.message.id);

  const mutation = useMutation({
    mutationFn: async () => {
      if (conversationId == null || siteId == null) {
        throw new Error("Missing conversation or site context");
      }
      return forkConversation(conversationId, messageId);
    },
    onSuccess: (fork) => {
      void queryClient.invalidateQueries({
        queryKey: ["conversations", "list", siteId],
      });
      router.push(`/${siteId}/conversation/${fork.id}`);
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
