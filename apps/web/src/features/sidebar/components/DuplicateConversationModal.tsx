"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { ConversationItem } from "@/features/sidebar/components/conversationSidebarTypes";

interface DuplicateConversationModalProps {
  target: ConversationItem | null;
  isDuplicating: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function DuplicateConversationModal({
  target,
  isDuplicating,
  onClose,
  onConfirm,
}: DuplicateConversationModalProps) {
  return (
    <Dialog open={target !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Duplicate conversation</DialogTitle>
          <DialogDescription>
            Creates a new conversation with the same messages. Future turns
            will diverge — the original is untouched.
          </DialogDescription>
        </DialogHeader>
        {target !== null && (
          <p className="rounded-md bg-muted/50 px-3 py-2 text-xs font-medium">
            {target.title}
          </p>
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={isDuplicating}
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            type="button"
            disabled={isDuplicating}
            onClick={onConfirm}
            data-testid="duplicate-conversation-confirm"
          >
            {isDuplicating ? "Duplicating…" : "Duplicate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
