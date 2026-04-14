import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/lib/components/ui/Label";
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
    <Dialog
      open={duplicateModal != null}
      onOpenChange={(open) => !open && setDuplicateModal(null)}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Duplicate strategy</DialogTitle>
        </DialogHeader>
        {duplicateModal && (
          <>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
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
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Description
                </Label>
                <Textarea
                  value={duplicateModal.description}
                  onChange={(event) =>
                    setDuplicateModal((prev) =>
                      prev ? { ...prev, description: event.target.value } : prev,
                    )
                  }
                  rows={3}
                  disabled={duplicateModal.isLoading}
                />
              </div>
              {duplicateModal.isLoading && (
                <div className="text-xs text-muted-foreground">
                  Loading strategy details...
                </div>
              )}
              {duplicateModal.error != null && (
                <div className="text-xs text-destructive">{duplicateModal.error}</div>
              )}
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setDuplicateModal(null)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={() => {
                  if (duplicateModal.isLoading) return;
                  const nameError = validateDuplicateName(duplicateModal.name);
                  if (nameError != null) {
                    setDuplicateModal((prev) =>
                      prev ? { ...prev, error: nameError } : prev,
                    );
                    return;
                  }
                  setDuplicateModal((prev) =>
                    prev ? startDuplicateSubmit(prev) : prev,
                  );
                  void (async () => {
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
                  })();
                }}
                disabled={duplicateModal.isSubmitting || duplicateModal.isLoading}
              >
                {duplicateModal.isSubmitting ? "Duplicating..." : "Duplicate"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
