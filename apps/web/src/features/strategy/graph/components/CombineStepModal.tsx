"use client";

import { Modal } from "@/shared/components/Modal";

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
        <div className="text-sm font-semibold text-slate-900">Create combine step</div>
        <div className="mt-1 text-[12px] text-slate-500">
          Choose how to combine the two selected steps.
        </div>
        <div className="mt-4 grid gap-2">
          {operators.map((operator) => (
            <button
              key={operator}
              type="button"
              onClick={() => onChoose(operator)}
              className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
            >
              <span className="font-semibold">{operator}</span>
              <span className="text-[11px] text-slate-500">
                {pendingCombine?.sourceId} + {pendingCombine?.targetId}
              </span>
            </button>
          ))}
        </div>
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="text-xs font-semibold uppercase tracking-wide text-slate-400 hover:text-slate-600"
          >
            Cancel
          </button>
        </div>
      </div>
    </Modal>
  );
}
