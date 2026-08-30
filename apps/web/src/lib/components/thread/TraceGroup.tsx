"use client";

import type { ReactElement } from "react";

import { PHASE_LABELS } from "@/lib/models/phaseRoles";
import { formatUsage } from "@/lib/utils/usageFormat";

import { TraceRow } from "./TraceRow";
import type { TraceGroupView } from "./traceTypes";

const LEAD = "lead";

export interface TraceGroupProps {
  group: TraceGroupView;
  bare: boolean;
  showRaw: boolean;
  showUsage: boolean;
  nameFor: (toolName: string) => string;
  labelFor?: (phase: string) => string;
}

function defaultLabel(phase: string): string {
  return PHASE_LABELS[phase] ?? phase;
}

export function TraceGroup({
  group,
  bare,
  showRaw,
  showUsage,
  nameFor,
  labelFor,
}: TraceGroupProps): ReactElement {
  const rows = group.rows.map((row) => (
    <TraceRow key={row.key} row={row} showRaw={showRaw} nameFor={nameFor} />
  ));
  if (bare) return <div>{rows}</div>;
  const label = (labelFor ?? defaultLabel)(group.phase);
  const usage = showUsage && group.tokens > 0;
  return (
    <div data-testid={group.key === LEAD ? undefined : "data-sub-agent-call"}>
      <div data-testid="trace-group" className="flex h-6 items-center gap-2">
        <span
          data-testid="trace-group-label"
          className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
        >
          {label}
        </span>
        {usage && (
          <span
            data-testid="trace-group-usage"
            className="text-[11px] text-muted-foreground tabular-nums"
          >
            {formatUsage(group.tokens, group.costUsd)}
          </span>
        )}
      </div>
      <div className="border-l border-border/50 pl-3">{rows}</div>
    </div>
  );
}
