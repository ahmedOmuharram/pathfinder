"use client";

import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils/cn";

export type SyncState = "idle" | "saving" | "error" | "paused";

interface EditorFooterProps {
  syncState: SyncState;
  /** Result count from useStepCounts. null = loading. -1 = unknown. */
  count: number | null;
  wdkUrl: string | null;
  onRetry?: () => void;
}

function SyncDot({ state }: { state: SyncState }) {
  const className = cn(
    "inline-block size-2 rounded-full",
    state === "idle" && "bg-emerald-500",
    state === "saving" && "bg-blue-500",
    state === "error" && "bg-destructive",
    state === "paused" && "bg-amber-500",
  );
  return <span className={className} aria-hidden />;
}

export function EditorFooter({ syncState, count, wdkUrl, onRetry }: EditorFooterProps) {
  return (
    <div
      className="flex items-center justify-between gap-3 border-t border-border px-4 py-3 text-xs text-muted-foreground"
      data-testid="step-editor-footer"
    >
      <div
        className="flex items-center gap-2"
        data-testid="step-editor-sync-state"
        data-sync-state={syncState}
      >
        {syncState === "saving" ? (
          <>
            <Spinner className="size-3" />
            <span>Saving…</span>
          </>
        ) : syncState === "error" ? (
          <>
            <SyncDot state="error" />
            <span className="text-destructive">Failed</span>
            {onRetry && (
              <Button variant="link" size="xs" onClick={onRetry} type="button">
                Retry
              </Button>
            )}
          </>
        ) : syncState === "paused" ? (
          <>
            <SyncDot state="paused" />
            <span className="text-amber-700">Sync paused (validation issue)</span>
          </>
        ) : (
          <>
            <SyncDot state="idle" />
            <span>Saved</span>
          </>
        )}
      </div>
      <div className="flex items-center gap-2">
        {count === null ? (
          <Skeleton className="h-3 w-12" />
        ) : count >= 0 ? (
          <span>{count.toLocaleString()} results</span>
        ) : null}
      </div>
      {wdkUrl != null && (
        <a
          href={wdkUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-foreground hover:underline"
        >
          View in WDK
          <ExternalLink className="size-3" />
        </a>
      )}
    </div>
  );
}
