"use client";

type StepEditorFooterProps = {
  onClose: () => void;
  onSave: () => void;
};

export function StepEditorFooter({ onClose, onSave }: StepEditorFooterProps) {
  return (
    <div className="flex items-center justify-end gap-3 border-t border-border px-5 py-3">
      <button
        onClick={onClose}
        className="rounded-md border border-transparent px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground transition-colors duration-150 hover:text-foreground"
      >
        Cancel
      </button>
      <button
        onClick={onSave}
        className="rounded-md bg-primary px-3 py-2 text-xs font-semibold uppercase tracking-wide text-primary-foreground transition-colors duration-150 hover:bg-primary/90"
      >
        Done
      </button>
    </div>
  );
}
