import { AlertTriangle } from "lucide-react";

export function BusyWorkerBanner() {
  return (
    <div
      role="status"
      className="flex items-center justify-center gap-2 border-b border-border bg-muted px-4 py-2 text-xs text-muted-foreground"
    >
      <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
      <span>
        The background service is not responding. New messages may take longer to
        answer.
      </span>
    </div>
  );
}
