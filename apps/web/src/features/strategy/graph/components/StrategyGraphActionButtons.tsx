"use client";

import { Loader2, Save } from "lucide-react";
import { useStrategyGraphCtx } from "@/features/strategy/graph/StrategyGraphContext";

export function StrategyGraphActionButtons() {
  const { canSave, handleSave, saveDisabledReason, isSaving, isUnsaved, onToast } =
    useStrategyGraphCtx();

  const saveIsDisabled = !canSave || isSaving;

  return (
    <div className="pointer-events-auto absolute bottom-4 right-4 z-10 flex flex-col gap-2">
      <div className="flex items-center justify-end gap-2 rounded-xl border border-border bg-card/90 p-2 shadow-sm backdrop-blur">
        <button
          type="button"
          onClick={() => {
            if (saveIsDisabled) {
              onToast?.({
                type: "warning",
                message: saveDisabledReason ?? "Cannot save.",
              });
              return;
            }
            void handleSave();
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
          className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors duration-150 hover:border-input hover:text-foreground ${
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
