"use client";

import { Modal } from "@/lib/components/Modal";

export interface PendingCombine {
  sourceId: string;
  targetId: string;
}

interface CombineStepModalProps {
  pendingCombine: PendingCombine | null;
  operators: readonly string[];
  onChoose: (operator: string) => void;
  onCancel: () => void;
}

export function CombineStepModal({
  pendingCombine,
  operators,
  onChoose,
  onCancel,
}: CombineStepModalProps) {
  return (
    <Modal
      open={!!pendingCombine}
      onClose={onCancel}
      title="Create combine step"
      maxWidth="max-w-md"
    >
      <div className="p-4">
        <div className="text-sm font-semibold text-foreground">Create combine step</div>
        <div className="mt-1 text-sm text-muted-foreground">
          Choose how to combine the two selected steps.
        </div>
        <div className="mt-4 grid gap-2">
          {operators.map((operator) => (
            <button
              key={operator}
              type="button"
              onClick={() => onChoose(operator)}
              className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm text-foreground transition-colors duration-150 hover:border-input hover:bg-accent"
            >
              <span className="font-semibold">{operator}</span>
              <span className="text-xs text-muted-foreground">
                {pendingCombine?.sourceId} + {pendingCombine?.targetId}
              </span>
            </button>
          ))}
        </div>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="text-xs font-semibold uppercase tracking-wide text-muted-foreground transition-colors duration-150 hover:text-foreground"
          >
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}
