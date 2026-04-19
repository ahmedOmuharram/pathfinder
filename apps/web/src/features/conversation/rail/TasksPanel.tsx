"use client";

import { Timer } from "lucide-react";

import { RailEmptyState, RailPanelShell } from "./RailPanelShell";

interface TasksPanelProps {
  conversationId: string;
}

export function TasksPanel({ conversationId: _ }: TasksPanelProps) {
  return (
    <RailPanelShell title="Tasks">
      <RailEmptyState
        icon={<Timer className="h-8 w-8" aria-hidden />}
        heading="No background tasks running"
        description="Long-running verification jobs (controls, enrichment, parameter optimization) show up here with live progress."
      />
    </RailPanelShell>
  );
}
