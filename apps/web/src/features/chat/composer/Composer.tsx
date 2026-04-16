"use client";

import { ComposerPrimitive } from "@assistant-ui/react";
import { Send } from "lucide-react";

export function Composer() {
  return (
    <ComposerPrimitive.Root className="flex flex-col gap-2 border-t bg-card px-4 py-3">
      <ComposerPrimitive.Input
        placeholder="Ask about strategies, genes, or data..."
        className="w-full resize-none rounded-md border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-ring"
        autoFocus
      />
      <div className="flex justify-end">
        <ComposerPrimitive.Send
          aria-label="Send"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50"
        >
          <Send className="h-4 w-4" /> Send
        </ComposerPrimitive.Send>
      </div>
    </ComposerPrimitive.Root>
  );
}
