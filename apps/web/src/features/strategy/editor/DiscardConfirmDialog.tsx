"use client";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface DiscardConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  changeCount: number;
  onConfirm: () => void;
}

export function DiscardConfirmDialog({
  open,
  onOpenChange,
  changeCount,
  onConfirm,
}: DiscardConfirmDialogProps) {
  const noun = changeCount === 1 ? "change" : "changes";
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent data-testid="step-editor-discard-confirm">
        <AlertDialogHeader>
          <AlertDialogTitle>
            Discard {changeCount} {noun}?
          </AlertDialogTitle>
          <AlertDialogDescription>
            This cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep editing</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            data-testid="step-editor-discard-confirm-button"
          >
            Discard
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
