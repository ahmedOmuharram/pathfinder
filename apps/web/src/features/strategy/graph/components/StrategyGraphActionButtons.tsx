"use client";

import { Save, Upload } from "lucide-react";

interface StrategyGraphActionButtonsProps {
  showPush: boolean;
  onPush?: () => void;
  canPush: boolean;
  isPushing: boolean;
  pushLabel: string;
  pushDisabledReason?: string;
  onPushDisabled?: () => void;

  canSave: boolean;
  onSave: () => void;
  onSaveDisabled?: () => void;
  saveDisabledReason?: string;
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
  onPushDisabled,
  canSave,
  onSave,
  onSaveDisabled,
  saveDisabledReason,
  isSaving,
  isUnsaved,
}: StrategyGraphActionButtonsProps) {
  const pushIsDisabled = !canPush || isPushing;
  const saveIsDisabled = !canSave || isSaving;
  return (
    <div className="pointer-events-auto absolute bottom-4 right-4 z-10 flex flex-col gap-2">
      <div className="flex items-center justify-end gap-2 rounded-xl border border-slate-200 bg-white/90 p-2 shadow-sm backdrop-blur">
        {showPush && onPush && (
          <button
            type="button"
            onClick={() => {
              if (pushIsDisabled) {
                onPushDisabled?.();
                return;
              }
              onPush();
            }}
            aria-disabled={pushIsDisabled}
            className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900 ${
              pushIsDisabled ? "cursor-not-allowed opacity-60" : ""
            }`}
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
          onClick={() => {
            if (saveIsDisabled) {
              onSaveDisabled?.();
              return;
            }
            onSave();
          }}
          aria-disabled={saveIsDisabled}
          className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 transition hover:border-slate-300 hover:text-slate-900 ${
            saveIsDisabled ? "cursor-not-allowed opacity-60" : ""
          } ${
            isUnsaved ? "save-attention" : ""
          }`}
          title={
            isSaving ? "Saving..." : !canSave && saveDisabledReason ? saveDisabledReason : "Save"
          }
        >
          <Save className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

