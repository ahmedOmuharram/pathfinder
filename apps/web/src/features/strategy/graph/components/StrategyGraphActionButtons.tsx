"use client";

import { AlertTriangle, Check, Loader2 } from "lucide-react";
import { useStrategyGraphCtx } from "@/features/strategy/graph/StrategyGraphContext";

export function StrategyGraphActionButtons() {
  const { syncStatus, lastSyncError } = useStrategyGraphCtx();

  // No indicator needed when idle or synced silently
  if (syncStatus === "idle") return null;

  return (
    <div className="pointer-events-auto absolute bottom-4 right-4 z-10 flex flex-col gap-2">
      <div className="flex items-center justify-end gap-2 rounded-xl border border-border bg-card/90 p-2 shadow-sm backdrop-blur">
        {syncStatus === "syncing" && (
          <div
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground"
            title="Syncing to VEuPathDB..."
            aria-label="Syncing to VEuPathDB"
          >
            <Loader2 className="h-4 w-4 animate-spin" />
          </div>
        )}
        {syncStatus === "synced" && (
          <div
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-emerald-600"
            title="Synced to VEuPathDB"
            aria-label="Synced to VEuPathDB"
          >
            <Check className="h-4 w-4" />
          </div>
        )}
        {syncStatus === "error" && (
          <div
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-destructive"
            title={lastSyncError ?? "Sync failed"}
            aria-label={lastSyncError ?? "Sync failed"}
          >
            <AlertTriangle className="h-4 w-4" />
          </div>
        )}
      </div>
    </div>
  );
}
