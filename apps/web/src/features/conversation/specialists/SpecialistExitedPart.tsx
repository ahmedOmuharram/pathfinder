import { CornerDownLeft } from "lucide-react";

export function SpecialistExitedPart() {
  return (
    <div
      data-testid="data-specialist-exited"
      data-specialist-bracket="close"
      className="my-2 flex items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground"
    >
      <CornerDownLeft className="size-3.5 shrink-0" aria-hidden />
      <span>Specialist session ended</span>
    </div>
  );
}
