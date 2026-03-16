import { Label } from "@/lib/components/ui/Label";
import { Modal } from "@/lib/components/Modal";
import { Input } from "@/lib/components/ui/Input";
import type { DuplicateModalState } from "@/features/sidebar/utils/duplicateModalState";
import {
  applyDuplicateSubmitFailure,
  startDuplicateSubmit,
  validateDuplicateName,
} from "@/features/sidebar/utils/duplicateModalState";

interface DuplicateStrategyModalProps {
  duplicateModal: DuplicateModalState | null;
  setDuplicateModal: React.Dispatch<React.SetStateAction<DuplicateModalState | null>>;
  onDuplicate: (itemId: string, name: string, description: string) => Promise<void>;
}

export function DuplicateStrategyModal({
  duplicateModal,
  setDuplicateModal,
  onDuplicate,
}: DuplicateStrategyModalProps) {
  return (
    <Modal
      open={!!duplicateModal}
      onClose={() => setDuplicateModal(null)}
      title="Duplicate strategy"
    >
      {duplicateModal && (
        <div className="p-4">
          <div className="mt-3 space-y-2">
            <Label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Name
            </Label>
            <Input
              value={duplicateModal.name}
              onChange={(event) =>
                setDuplicateModal((prev) =>
                  prev ? { ...prev, name: event.target.value } : prev,
                )
              }
              disabled={duplicateModal.isLoading}
            />
            <Label className="block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Description
            </Label>
            <textarea
              value={duplicateModal.description}
              onChange={(event) =>
                setDuplicateModal((prev) =>
                  prev ? { ...prev, description: event.target.value } : prev,
                )
              }
              rows={3}
              disabled={duplicateModal.isLoading}
              className="w-full resize-none rounded-md border border-border px-3 py-2 text-sm text-foreground"
            />
            {duplicateModal.isLoading && (
              <div className="text-xs text-muted-foreground">
                Loading strategy details...
              </div>
            )}
            {duplicateModal.error && (
              <div className="text-xs text-destructive">{duplicateModal.error}</div>
            )}
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setDuplicateModal(null)}
              className="rounded-md px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={async () => {
                if (!duplicateModal || duplicateModal.isLoading) return;
                const nameError = validateDuplicateName(duplicateModal.name);
                if (nameError) {
                  setDuplicateModal((prev) =>
                    prev ? { ...prev, error: nameError } : prev,
                  );
                  return;
                }
                setDuplicateModal((prev) => (prev ? startDuplicateSubmit(prev) : prev));
                try {
                  await onDuplicate(
                    duplicateModal.item.id,
                    duplicateModal.name.trim(),
                    duplicateModal.description.trim(),
                  );
                  setDuplicateModal(null);
                } catch {
                  setDuplicateModal((prev) =>
                    prev ? applyDuplicateSubmitFailure(prev) : prev,
                  );
                }
              }}
              disabled={duplicateModal.isSubmitting || duplicateModal.isLoading}
              className="rounded-md bg-primary px-3 py-2 text-xs font-semibold uppercase tracking-wide text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
            >
              {duplicateModal.isSubmitting ? "Duplicating..." : "Duplicate"}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
