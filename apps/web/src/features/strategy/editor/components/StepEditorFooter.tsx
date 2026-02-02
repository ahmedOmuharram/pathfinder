"use client";

type StepEditorFooterProps = {
  onClose: () => void;
  onSave: () => void;
};

export function StepEditorFooter({ onClose, onSave }: StepEditorFooterProps) {
  return (
    <div className="flex items-center justify-end gap-3 border-t border-slate-200 px-5 py-3">
      <button
        onClick={onClose}
        className="rounded-md border border-transparent px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500 transition-colors hover:text-slate-800"
      >
        Cancel
      </button>
      <button
        onClick={onSave}
        className="rounded-md bg-slate-900 px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-white transition-colors hover:bg-slate-700"
      >
        Done
      </button>
    </div>
  );
}
