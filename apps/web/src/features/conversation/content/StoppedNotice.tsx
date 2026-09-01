import { CircleStop } from "lucide-react";

export function StoppedNotice() {
  return (
    <div
      data-testid="stopped-notice"
      className="flex items-center gap-2 text-xs text-muted-foreground"
    >
      <CircleStop className="size-3.5 shrink-0" aria-hidden />
      <span>You stopped this response.</span>
    </div>
  );
}
