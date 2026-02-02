"use client";

import { Save, Upload } from "lucide-react";

interface StrategyGraphActionButtonsProps {
  showPush: boolean;
  onPush?: () => void;
  canPush: boolean;
  isPushing: boolean;
  pushLabel: string;
  pushDisabledReason?: string;

  canSave: boolean;
  onSave: () => void;
  isSaving: boolean;
  isUnsaved: boolean;
}

export function StrategyGraphActionButtons({
  showPush,
  onPush,
  canPush,
  isPushing,
  pushLabel,
  pushDisabledReason,
  canSave,
  onSave,
  isSaving,
  isUnsaved,
}: StrategyGraphActionButtonsProps) {
  return (
    <div className="pointer-events-auto absolute right-4 top-4 z-10 flex flex-col gap-2">
      <div className="flex items-center justify-end gap-2 rounded-xl border border-slate-200 bg-white/90 p-2 shadow-sm backdrop-blur">
        {showPush && onPush && (
          <button
            type="button"
            onClick={onPush}
            disabled={!canPush || isPushing}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-60"
            title={
              isPushing
                ? "Pushing..."
                : !canPush && pushDisabledReason
                  ? pushDisabledReason
                  : pushLabel
            }
          >
            <Upload className="h-4 w-4" />
          </button>
        )}

        <button
          type="button"
          onClick={onSave}
          disabled={!canSave}
          className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-60 ${
            isUnsaved ? "save-attention" : ""
          }`}
          title={isSaving ? "Saving..." : "Save"}
        >
          <Save className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

