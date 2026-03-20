"use client";

import { AlertTriangle, Sparkles } from "lucide-react";
import type { SubKaniActivity } from "@pathfinder/shared";
import { Card } from "@/lib/components/ui/Card";
import type {
  DelegateSummary,
  RejectedDelegateSummary,
} from "@/features/chat/utils/extractDelegateSummaries";
import { formatCompact, formatCost } from "@/lib/utils/format";
import { SubAgentCard } from "./SubAgentCard";

interface DelegationPanelProps {
  subKaniActivity: SubKaniActivity;
  delegateSummaries?: DelegateSummary[];
  delegateRejected?: RejectedDelegateSummary[];
}

export function DelegationPanel({
  subKaniActivity,
  delegateSummaries,
  delegateRejected,
}: DelegationPanelProps) {
  const entries = Object.entries(subKaniActivity.calls || {});
  const agentCount = entries.length;

  // Aggregate token usage
  const tokenUsageMap = subKaniActivity.tokenUsage;
  let totalTokens = 0;
  let totalCost = 0;
  let hasTokenData = false;

  if (tokenUsageMap) {
    for (const usage of Object.values(tokenUsageMap)) {
      totalTokens += usage.promptTokens + usage.completionTokens;
      totalCost += usage.estimatedCostUsd;
      hasTokenData = true;
    }
  }

  return (
    <Card className="rounded-md p-2 space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
        <span>
          Delegated to {agentCount} sub-agent{agentCount !== 1 ? "s" : ""}
        </span>
        {hasTokenData && (
          <span className="ml-auto font-normal normal-case tracking-normal">
            {formatCompact(totalTokens)} tokens &middot; ~{formatCost(totalCost)}
          </span>
        )}
      </div>

      {/* Cards */}
      <div className="space-y-2">
        {entries.map(([task, toolCalls]) => {
          const matchingSummary = delegateSummaries?.find(
            (s) => s.task === task || task.startsWith(s.task),
          );

          const statusVal = subKaniActivity.status?.[task];
          const modelVal = subKaniActivity.models?.[task];
          const tokenVal = subKaniActivity.tokenUsage?.[task];
          return (
            <SubAgentCard
              key={task}
              task={task}
              toolCalls={toolCalls}
              status={statusVal ?? "done"}
              {...(modelVal != null ? { modelId: modelVal } : {})}
              {...(tokenVal != null ? { tokenUsage: tokenVal } : {})}
              {...(matchingSummary?.instructions != null
                ? { instructions: matchingSummary.instructions }
                : {})}
              {...(matchingSummary?.steps != null
                ? { steps: matchingSummary.steps }
                : {})}
              {...(matchingSummary?.notes != null
                ? { notes: matchingSummary.notes }
                : {})}
            />
          );
        })}
      </div>

      {/* Rejected section */}
      {delegateRejected && delegateRejected.length > 0 && (
        <details className="rounded-md border border-border bg-muted/30 p-2">
          <summary className="cursor-pointer select-none text-xs font-semibold text-amber-500 flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
            {delegateRejected.length} rejected subtask
            {delegateRejected.length !== 1 ? "s" : ""}
          </summary>
          <ul className="mt-1.5 space-y-1 text-xs text-muted-foreground">
            {delegateRejected.map((entry, idx) => (
              <li key={`${entry.task ?? "rejected"}-${idx}`}>
                {entry.task ?? "Subtask"}: {entry.error ?? "Rejected"}
                {entry.details && <span> &middot; {entry.details}</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}
