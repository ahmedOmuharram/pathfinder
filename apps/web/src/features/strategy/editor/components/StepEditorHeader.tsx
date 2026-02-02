"use client";

type StepEditorHeaderProps = {
  onClose: () => void;
};

export function StepEditorHeader({ onClose }: StepEditorHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-700">
        Edit Step
      </h3>
      <button
        onClick={onClose}
        className="p-1 text-slate-400 transition-colors hover:text-slate-700"
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
