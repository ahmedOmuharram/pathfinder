import type { ToolCall } from "@pathfinder/shared";
import { ToolCallInspector } from "@/features/chat/components/message/ToolCallInspector";
import { Card } from "@/lib/components/ui/Card";

/**
 * Compact animated dots shown while waiting for the model to produce
 * reasoning or tool calls. Replaces the old heavy "Waiting for..." panel.
 */
function PulsingDots() {
  return (
    <div className="flex animate-fade-in justify-start">
      <Card className="flex items-center gap-1 px-4 py-2.5">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:0ms]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:150ms]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground [animation-delay:300ms]" />
      </Card>
    </div>
  );
}

export function ThinkingPanel(props: {
  isStreaming: boolean;
  activeToolCalls: ToolCall[];
  lastToolCalls: ToolCall[];
  reasoning?: string | null;
  title?: string;
}) {
  const {
    isStreaming,
    activeToolCalls,
    lastToolCalls,
    reasoning,
    title,
  } = props;
  const hasReasoning = Boolean(reasoning && reasoning.trim().length > 0);
  const hasAnyContent =
    hasReasoning ||
    activeToolCalls.length > 0 ||
    lastToolCalls.length > 0;

  // Nothing to show and not streaming — hide entirely.
  if (!isStreaming && !hasAnyContent) return null;

  // Streaming but no content yet — show compact animated dots; parent provides 85% width.
  if (isStreaming && !hasAnyContent) {
    return (
      <div className="w-full animate-fade-in">
        <PulsingDots />
      </div>
    );
  }

  return (
    <div className="flex w-full justify-start animate-fade-in">
      <div className="w-full">
        <details
          open
          className="w-full rounded-lg border border-border bg-card px-3 py-2"
        >
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {title || "Thinking"}
          </summary>
          <div className="mt-2 space-y-3 text-sm text-foreground">
            {hasReasoning && (
              <div className="rounded-md border border-border bg-card p-2">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Reasoning
                </div>
                <pre className="whitespace-pre-wrap break-words text-xs text-foreground">
                  {reasoning}
                </pre>
              </div>
            )}
            {activeToolCalls.length > 0 && (
              <div className="rounded-md border border-border bg-muted p-2">
                <ToolCallInspector toolCalls={activeToolCalls} isActive />
              </div>
            )}

            {lastToolCalls.length > 0 && (
              <div className="rounded-md border border-border bg-card p-2">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Recent Tool Output
                </div>
                <ToolCallInspector toolCalls={lastToolCalls} />
              </div>
            )}
          </div>
        </details>
      </div>
    </div>
  );
}
