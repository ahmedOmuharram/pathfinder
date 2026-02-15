"use client";

import { Loader2, Save } from "lucide-react";

interface StrategyGraphActionButtonsProps {
  canSave: boolean;
  onSave: () => void;
  onSaveDisabled?: () => void;
  saveDisabledReason?: string;
  isSaving: boolean;
  isUnsaved: boolean;
}

export function StrategyGraphActionButtons({
  canSave,
  onSave,
  onSaveDisabled,
  saveDisabledReason,
  isSaving,
  isUnsaved,
}: StrategyGraphActionButtonsProps) {
  const saveIsDisabled = !canSave || isSaving;
  return (
    <div className="pointer-events-auto absolute bottom-4 right-4 z-10 flex flex-col gap-2">
      <div className="flex items-center justify-end gap-2 rounded-xl border border-slate-200 bg-white/90 p-2 shadow-sm backdrop-blur">
        <button
          type="button"
          onClick={() => {
            if (saveIsDisabled) {
              onSaveDisabled?.();
              return;
            }
            onSave();
          }}
          aria-disabled={saveIsDisabled}
          aria-label={
            isSaving
              ? "Saving strategy\u2026"
              : !canSave && saveDisabledReason
                ? saveDisabledReason
                : isUnsaved
                  ? "Save (unsaved changes)"
                  : "Save"
          }
          className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900 ${
            saveIsDisabled ? "cursor-not-allowed opacity-60" : ""
          } ${isUnsaved ? "save-attention" : ""}`}
          title={
            isSaving
              ? "Saving\u2026"
              : !canSave && saveDisabledReason
                ? saveDisabledReason
                : isUnsaved
                  ? "Save (unsaved changes)"
                  : "Save"
          }
        >
          {isSaving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  );
}
