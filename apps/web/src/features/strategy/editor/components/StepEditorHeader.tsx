"use client";

type StepEditorHeaderProps = {
  onClose: () => void;
};

export function StepEditorHeader({ onClose }: StepEditorHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-border px-5 py-3">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-foreground">
        Edit Step
      </h3>
      <button
        onClick={onClose}
        className="p-1 text-muted-foreground transition-colors duration-150 hover:text-foreground"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          className="h-4 w-4"
        >
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
