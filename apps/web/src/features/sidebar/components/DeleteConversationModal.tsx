"use client";

import { useState } from "react";

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

interface DeleteConversationModalProps {
  target: ConversationItem | null;
  isDeleting: boolean;
  /** Count of descendant conversations in this branch's subtree. */
  descendantCount: number;
  onClose: () => void;
  onConfirmDelete: (options: { cascade: boolean }) => void;
}

export function DeleteConversationModal({
  target,
  isDeleting,
  descendantCount,
  onClose,
  onConfirmDelete,
}: DeleteConversationModalProps) {
  const [cascade, setCascade] = useState(false);
  const [lastTargetId, setLastTargetId] = useState<string | null>(null);

  // Reset cascade whenever the target changes (render-time, no effect).
  const currentId = target?.id ?? null;
  if (currentId !== lastTargetId) {
    setLastTargetId(currentId);
    if (cascade) setCascade(false);
  }

  const hasChildren = descendantCount > 0;

  return (
    <Dialog
      open={target !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Delete conversation</DialogTitle>
          <DialogDescription>
            Delete{" "}
            <span className="font-semibold text-foreground">
              &ldquo;{target?.title}&rdquo;
            </span>
            ? This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        {hasChildren && (
          <label className="mt-2 flex cursor-pointer items-start gap-2 rounded-md border border-border p-3 text-sm">
            <input
              type="checkbox"
              checked={cascade}
              onChange={(e) => setCascade(e.target.checked)}
              disabled={isDeleting}
              className="mt-0.5 h-4 w-4 rounded border-input"
            />
            <div className="space-y-0.5">
              <div className="font-medium">
                Also delete {descendantCount} sub-
                {descendantCount === 1 ? "branch" : "branches"}
              </div>
              <p className="text-xs text-muted-foreground">
                Unchecked: sub-branches move up one level and keep their fork point.
                Checked: the whole subtree is removed.
              </p>
            </div>
          </label>
        )}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={() => onConfirmDelete({ cascade })}
            disabled={isDeleting}
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
