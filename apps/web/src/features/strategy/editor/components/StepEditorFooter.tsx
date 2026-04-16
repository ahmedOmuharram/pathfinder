"use client";

type StepEditorFooterProps = {
  onClose: () => void;
};

export function StepEditorFooter({ onClose }: StepEditorFooterProps) {
  return (
    <div className="flex items-center justify-end gap-3 border-t border-border px-5 py-3">
      <button
        type="button"
        onClick={onClose}
        className="rounded-md border border-transparent px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground transition-colors duration-150 hover:text-foreground"
      >
        Cancel
      </button>
      <button
        type="submit"
        className="rounded-md bg-primary px-3 py-2 text-xs font-semibold uppercase tracking-wide text-primary-foreground transition-colors duration-150 hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Done
      </button>
    </div>
  );
}
