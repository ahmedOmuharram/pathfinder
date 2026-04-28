"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const LABEL_CLASS =
  "text-xs font-semibold uppercase tracking-wide text-muted-foreground";

interface SaveSubstrategyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultName: string;
  isSaving: boolean;
  onConfirm: (input: { name: string; description: string }) => void;
}

export function SaveSubstrategyDialog({
  open,
  onOpenChange,
  defaultName,
  isSaving,
  onConfirm,
}: SaveSubstrategyDialogProps) {
  const [name, setName] = useState(defaultName);
  const [description, setDescription] = useState("");
  const [lastOpenSeed, setLastOpenSeed] = useState<string | null>(
    open ? defaultName : null,
  );
  // Reset on each open transition (closed -> open) without an effect: the
  // render-time state compare matches React Compiler conventions.
  if (open && lastOpenSeed !== defaultName) {
    setLastOpenSeed(defaultName);
    setName(defaultName);
    setDescription("");
  }
  if (!open && lastOpenSeed !== null) {
    setLastOpenSeed(null);
  }

  const submit = (): void => {
    const trimmed = name.trim();
    if (trimmed === "") return;
    onConfirm({ name: trimmed, description: description.trim() });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="save-substrategy-dialog">
        <DialogHeader>
          <DialogTitle>Save as reusable strategy</DialogTitle>
          <DialogDescription>
            Saves this step and everything feeding into it as a new strategy
            in the saved-strategy library. Other conversations can insert it
            without re-running the searches.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="space-y-1">
            <label htmlFor="save-substrategy-name" className={LABEL_CLASS}>
              Name
            </label>
            <Input
              id="save-substrategy-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={255}
              autoFocus
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="save-substrategy-desc" className={LABEL_CLASS}>
              Description (optional)
            </label>
            <Textarea
              id="save-substrategy-desc"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={2000}
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={submit}
            disabled={isSaving || name.trim() === ""}
            data-testid="save-substrategy-confirm"
          >
            {isSaving ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
