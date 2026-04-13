"use client";

import { useChatSessionContext } from "./approval/useChatContext";

const PHASE_LABEL: Record<string, string> = {
  scoping: "Scoping the problem",
  discovery: "Discovering WDK searches",
  planning: "Planning the strategy",
  execution: "Executing the strategy",
  verification: "Verifying results",
};

export function StreamingIndicator() {
  const session = useChatSessionContext();
  const last = session.messages[session.messages.length - 1];
  const phase =
    last?.role === "assistant"
      ? ((last.metadata as { phase?: string } | undefined)?.phase ?? "")
      : "";
  const label = PHASE_LABEL[phase] ?? "Thinking";

  return (
    <div
      data-testid="streaming-indicator"
      data-phase={phase || undefined}
      className="my-2 mr-auto flex w-full max-w-full items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-foreground"
    >
      <div className="flex items-center gap-1" aria-hidden="true">
        <span className="block h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-120ms]" />
        <span className="block h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:-60ms]" />
        <span className="block h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" />
      </div>
      <span className="text-xs text-muted-foreground">{label}…</span>
    </div>
  );
}
