"use client";

import { Bookmark } from "lucide-react";

import { cn } from "@/lib/utils/cn";

interface SavedStrategyPillProps {
  name: string;
  indented?: boolean;
}

export function SavedStrategyPill({ name, indented = false }: SavedStrategyPillProps) {
  return (
    <div
      className={cn(
        "flex w-full items-center gap-2 rounded-md border border-dashed border-primary/40 bg-primary/5 px-2 py-1.5 text-left text-xs",
        indented && "ml-4",
      )}
      data-testid="saved-strategy-pill"
    >
      <Bookmark className="size-3 shrink-0 text-primary" aria-hidden />
      <span className="flex-1 truncate font-medium text-foreground">{name}</span>
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
        saved
      </span>
    </div>
  );
}
