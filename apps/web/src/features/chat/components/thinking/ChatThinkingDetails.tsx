"use client";

import type { ToolCall, SubKaniActivity } from "@pathfinder/shared";
import { ToolCallInspector } from "@/features/chat/components/message/ToolCallInspector";
import type {
  DelegateSummary,
  RejectedDelegateSummary,
} from "@/features/chat/utils/extractDelegateSummaries";
import { DelegationPanel } from "./DelegationPanel";

interface ChatThinkingDetailsProps {
  toolCalls?: ToolCall[] | null;
  delegateSummaries?: DelegateSummary[];
  delegateRejected?: RejectedDelegateSummary[];
  subKaniActivity?: SubKaniActivity | null;
  reasoning?: string | null;
  title?: string;
}

export function ChatThinkingDetails({
  toolCalls,
  delegateSummaries = [],
  delegateRejected = [],
  subKaniActivity,
  reasoning,
  title,
}: ChatThinkingDetailsProps) {
  const hasToolCalls = (toolCalls?.length ?? 0) > 0;
  const hasSubKaniActivity = Object.keys(subKaniActivity?.calls ?? {}).length > 0;
  const hasDelegate = delegateSummaries.length > 0 || delegateRejected.length > 0;
  const hasReasoning = Boolean(reasoning && reasoning.trim().length > 0);

  if (!hasToolCalls && !hasSubKaniActivity && !hasDelegate && !hasReasoning)
    return null;

  return (
    <details className="rounded-lg border border-border bg-card px-3 py-2">
      <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title ?? "Thinking"}
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
        {hasToolCalls && (
          <div className="rounded-md border border-border bg-muted p-2">
            <ToolCallInspector toolCalls={toolCalls ?? []} />
          </div>
        )}

        {(hasSubKaniActivity || delegateSummaries.length > 0) && (
          <DelegationPanel
            subKaniActivity={subKaniActivity!}
            delegateSummaries={delegateSummaries}
            delegateRejected={delegateRejected}
          />
        )}
      </div>
    </details>
  );
}
