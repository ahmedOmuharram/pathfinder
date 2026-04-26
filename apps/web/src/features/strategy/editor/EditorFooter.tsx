"use client";

import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils/cn";

export type SyncState = "idle" | "saving" | "error" | "paused";

interface EditorFooterProps {
  syncState: SyncState;
  changeCount: number;
  isSaving: boolean;
  onSave: () => void;
  onDiscard: () => void;
  /** Result count from useStepCounts. null = loading. -1 = unknown. */
  count: number | null;
  wdkUrl: string | null;
  /** Display name of the host site (e.g. "PlasmoDB") for the View link. */
  dbName: string;
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

export function EditorFooter({
  syncState,
  changeCount,
  isSaving,
  onSave,
  onDiscard,
  count,
  wdkUrl,
  dbName,
}: EditorFooterProps) {
  const hasChanges = changeCount > 0;
  return (
    <div
      className="flex flex-col gap-2 border-t border-border px-4 py-3 text-xs text-muted-foreground"
      data-testid="step-editor-footer"
    >
      <div className="flex items-center justify-between gap-3">
        <div
          className="flex items-center gap-2"
          data-testid="step-editor-sync-state"
          data-sync-state={syncState}
          data-change-count={changeCount}
        >
          {isSaving ? (
            <>
              <Spinner className="size-3" />
              <span>Saving…</span>
            </>
          ) : syncState === "error" ? (
            <>
              <SyncDot state="error" />
              <span className="text-destructive">Save failed</span>
            </>
          ) : syncState === "paused" ? (
            <>
              <SyncDot state="paused" />
              <span className="text-amber-700">Sync paused (validation issue)</span>
            </>
          ) : hasChanges ? (
            <>
              <SyncDot state="saving" />
              <span data-testid="step-editor-change-count">
                Edited: {changeCount} {changeCount === 1 ? "change" : "changes"}
              </span>
            </>
          ) : (
            <>
              <SyncDot state="idle" />
              <span>All changes saved</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          {count === null ? (
            <Skeleton className="h-3 w-12" />
          ) : count >= 0 ? (
            <span>{count.toLocaleString()} results</span>
          ) : null}
          {wdkUrl != null && (
            <a
              href={wdkUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-foreground hover:underline"
            >
              View in {dbName !== "" ? dbName : "WDK"}
              <ExternalLink className="size-3" />
            </a>
          )}
        </div>
      </div>
      {hasChanges && (
        <div className="flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onDiscard}
            disabled={isSaving}
            data-testid="step-editor-discard"
          >
            Discard
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={onSave}
            disabled={isSaving}
            data-testid="step-editor-save"
          >
            {isSaving ? "Saving…" : "Save"}
          </Button>
        </div>
      )}
    </div>
  );
}
