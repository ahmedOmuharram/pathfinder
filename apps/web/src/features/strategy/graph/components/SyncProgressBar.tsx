"use client";

import { cn } from "@/lib/utils/cn";

interface SyncProgressBarProps {
  active: boolean;
}

export function SyncProgressBar({ active }: SyncProgressBarProps) {
  return (
    <div
      data-testid="canvas-sync-progress"
      data-active={active ? "true" : "false"}
      aria-hidden={!active}
      className={cn(
        "pointer-events-none absolute inset-x-0 top-0 z-50 h-0.5 overflow-hidden bg-transparent transition-opacity duration-200",
        active ? "opacity-100" : "opacity-0",
      )}
    >
      <div
        className={cn(
          "h-full w-1/3 -translate-x-full rounded-full bg-primary",
          active && "animate-sync-progress",
        )}
      />
    </div>
  );
}
