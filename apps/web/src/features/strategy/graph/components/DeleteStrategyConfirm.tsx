"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface DeleteStrategyConfirmProps {
  open: boolean;
  strategyName: string;
  isDeleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DeleteStrategyConfirm({
  open,
  strategyName,
  isDeleting,
  onCancel,
  onConfirm,
}: DeleteStrategyConfirmProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !isDeleting) onCancel();
      }}
    >
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Delete strategy</DialogTitle>
          <DialogDescription>
            Delete{" "}
            <span className="font-semibold text-foreground">
              &ldquo;{strategyName}&rdquo;
            </span>
            ? This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            disabled={isDeleting}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={onConfirm}
            disabled={isDeleting}
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
