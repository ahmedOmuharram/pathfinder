"use client";

import { useState, type ReactNode } from "react";
import { ChevronRight } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils/cn";

interface AdvancedParamsGroupProps {
  children: ReactNode;
  count: number;
  hasErrors?: boolean;
}

export function AdvancedParamsGroup({
  children,
  count,
  hasErrors = false,
}: AdvancedParamsGroupProps) {
  const [open, setOpen] = useState(false);
  if (count === 0) return null;

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className={cn(
        "rounded-lg border bg-card px-3 py-2",
        hasErrors ? "border-destructive/30" : "border-border",
      )}
    >
      <CollapsibleTrigger className="flex w-full items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground select-none">
        <ChevronRight
          className={cn(
            "size-3.5 transition-transform duration-150",
            open ? "rotate-90" : "",
          )}
        />
        Advanced Parameters ({count})
        {hasErrors && (
          <span className="ml-2 text-destructive" aria-label="has errors">
            !
          </span>
        )}
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2 space-y-3">{children}</CollapsibleContent>
    </Collapsible>
  );
}
