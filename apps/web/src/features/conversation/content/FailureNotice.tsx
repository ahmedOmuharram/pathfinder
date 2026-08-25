import { ActionBarPrimitive } from "@assistant-ui/react";
import { AlertTriangle, RefreshCw } from "lucide-react";

/** The failure card, shown live from the error chunk and after a reload from
 * the `data-turn-failed` part. */
export function FailureNotice({ detail }: { detail: string }) {
  return (
    <div
      data-testid="failure-notice"
      className="my-2 flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium">Response failed</p>
        <p className="mt-0.5 break-words text-xs text-destructive">{detail}</p>
        <ActionBarPrimitive.Reload asChild>
          <button
            type="button"
            className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-destructive/40 bg-background px-2 py-1 text-xs font-medium text-destructive shadow-sm transition-colors hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive"
          >
            <RefreshCw className="size-3" aria-hidden />
            Try again
          </button>
        </ActionBarPrimitive.Reload>
      </div>
    </div>
  );
}
