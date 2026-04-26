"use client";

import { Button } from "@/components/ui/button";

interface RecoveryBannerProps {
  onRestore: () => void;
  onDismiss: () => void;
}

export function RecoveryBanner({ onRestore, onDismiss }: RecoveryBannerProps) {
  return (
    <div
      className="flex items-center justify-between gap-2 border-b border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-900"
      data-testid="step-editor-recovery-banner"
    >
      <span>Restore unsaved changes from last session?</span>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="xs"
          onClick={onRestore}
          data-testid="step-editor-recovery-restore"
        >
          Restore
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="xs"
          onClick={onDismiss}
          data-testid="step-editor-recovery-discard"
        >
          Discard
        </Button>
      </div>
    </div>
  );
}
