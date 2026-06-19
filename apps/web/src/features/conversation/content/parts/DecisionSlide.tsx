"use client";

import { Check, PencilLine } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function ChangeRequest({
  open,
  onToggle,
  text,
  onText,
  onSubmit,
}: {
  open: boolean;
  onToggle: () => void;
  text: string;
  onText: (t: string) => void;
  onSubmit: () => void;
}) {
  return (
    <div>
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground hover:text-foreground"
        data-testid="carousel-request-changes-toggle"
        aria-expanded={open}
      >
        <PencilLine className="size-3.5" aria-hidden /> Request changes
      </button>
      {open && (
        <div className="mt-1.5 space-y-1.5">
          <Textarea
            value={text}
            onChange={(e) => onText(e.target.value)}
            placeholder="Describe what to change..."
            rows={2}
            data-testid="carousel-request-changes-input"
          />
          <div className="flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={text.trim() === ""}
              onClick={onSubmit}
              data-testid="carousel-request-changes-send"
            >
              Send
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function ApproveRow({
  submitLabel,
  onSubmit,
  changeOpen,
  onToggleChange,
  changeText,
  onChangeText,
  onRequestChanges,
}: {
  submitLabel: string;
  onSubmit: () => void;
  changeOpen: boolean;
  onToggleChange: () => void;
  changeText: string;
  onChangeText: (t: string) => void;
  onRequestChanges: () => void;
}) {
  return (
    <div className="space-y-2">
      <Button
        type="button"
        size="sm"
        className="w-full"
        onClick={onSubmit}
        data-testid="carousel-approve-run"
      >
        <Check className="mr-1 size-4" aria-hidden /> {submitLabel}
      </Button>
      <ChangeRequest
        open={changeOpen}
        onToggle={onToggleChange}
        text={changeText}
        onText={onChangeText}
        onSubmit={onRequestChanges}
      />
    </div>
  );
}
