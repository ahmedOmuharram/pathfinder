"use client";

import { useEditComposer, useMessage } from "@assistant-ui/react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { forkStrategy } from "@pathfinder/shared/generated/hooks/useForkStrategy";
import { revertToMessage } from "@pathfinder/shared/generated/hooks/useRevertToMessage";
import { submitProductAction } from "@pathfinder/shared/generated/hooks/useSubmitProductAction";
import { strategyQueryKey } from "@/lib/api/strategy";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";

import { extractTraceId } from "../runtime/traceId";
import { BranchOrRevertDialog } from "./BranchOrRevertDialog";

const ROUTE_RE = /^\/([^/]+)\/conversation\/([^/?#]+)/;

export function EditComposerBranchOrRevert() {
  const messageId = useMessage((s) => s.id);
  const parentId = useMessage((s) => s.parentId);
  const fullMessage = useMessage((s) => s);
  const composerText = useEditComposer((s) => s.text);
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const setPendingSubmission = useSessionStore((s) => s.setPendingUserSubmission);
  const bumpChatResetCounter = useSessionStore((s) => s.bumpChatResetCounter);

  const [dialogOpen, setDialogOpen] = useState(false);

  const match = pathname.match(ROUTE_RE);
  const siteId = match?.[1] ?? null;
  const conversationId = match?.[2] ?? null;

  const branchMutation = useMutation({
    mutationFn: async () => {
      if (conversationId === null || siteId === null || parentId === null) {
        throw new Error("Cannot branch from here");
      }
      return forkStrategy(conversationId, { fromMessageId: parentId });
    },
    onSuccess: (fork) => {
      if (siteId === null) return;
      setPendingSubmission({
        conversationId: fork.id,
        content: composerText.trim(),
      });
      setDialogOpen(false);
      router.push(`/${siteId}/conversation/${fork.id}`);
    },
    onError: (err) => {
      toast.error(toUserMessage(err, "Failed to branch"));
    },
  });

  const revertMutation = useMutation({
    mutationFn: async () => {
      if (conversationId === null) throw new Error("No conversation");
      await revertToMessage(conversationId, { messageId });
      const traceId = extractTraceId(fullMessage);
      void submitProductAction({
        action: "undo_turn",
        streamId: messageId,
        ...(traceId !== null && { traceId }),
      }).catch((err: unknown) => {
        console.warn("submitProductAction(undo_turn) failed", err);
      });
    },
    onSuccess: async () => {
      if (conversationId === null) return;
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["conversations", conversationId, "messages"],
        }),
        queryClient.invalidateQueries({
          queryKey: strategyQueryKey(conversationId),
        }),
        queryClient.invalidateQueries({
          queryKey: ["conversations", conversationId, "scratchpad"],
        }),
      ]);
      setPendingSubmission({
        conversationId,
        content: composerText.trim(),
      });
      bumpChatResetCounter();
      setDialogOpen(false);
    },
    onError: (err) => {
      toast.error(toUserMessage(err, "Failed to revert"));
    },
  });

  const pending = branchMutation.isPending || revertMutation.isPending;

  const handleClick = () => {
    if (composerText.trim() === "") return;
    setDialogOpen(true);
  };

  return (
    <>
      <Button
        type="button"
        size="sm"
        onClick={handleClick}
        disabled={pending || composerText.trim() === ""}
        data-testid="edit-composer-branch-or-revert"
      >
        Save…
      </Button>
      <BranchOrRevertDialog
        open={dialogOpen}
        canBranch={parentId !== null}
        pending={pending}
        onBranch={() => branchMutation.mutate()}
        onRevert={() => revertMutation.mutate()}
        onCancel={() => setDialogOpen(false)}
      />
    </>
  );
}
