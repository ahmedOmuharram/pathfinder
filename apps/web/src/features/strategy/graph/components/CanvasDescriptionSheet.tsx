"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateStrategyMetaMutation } from "@/features/strategy/mutations";

interface CanvasDescriptionSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialDescription: string;
}

export function CanvasDescriptionSheet({
  open,
  onOpenChange,
  initialDescription,
}: CanvasDescriptionSheetProps) {
  const updateMeta = useUpdateStrategyMetaMutation();
  const [draft, setDraft] = useState(initialDescription);
  const [prev, setPrev] = useState(initialDescription);

  if (open && initialDescription !== prev) {
    setPrev(initialDescription);
    setDraft(initialDescription);
  }

  const save = (): void => {
    updateMeta.mutate({ description: draft.trim() });
    onOpenChange(false);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-[420px] flex-col gap-0 p-0 sm:max-w-[420px]"
      >
        <SheetHeader className="border-b border-border">
          <SheetTitle>Edit description</SheetTitle>
          <SheetDescription>
            A short note to help you remember what this strategy is for.
          </SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-auto p-4">
          <Textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            rows={8}
            placeholder="Add a description"
            aria-label="Strategy description"
            className="resize-none"
          />
        </div>
        <SheetFooter className="border-t border-border">
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={save}>Save</Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
