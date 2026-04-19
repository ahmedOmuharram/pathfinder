"use client";

import { Brain } from "lucide-react";

import { RailEmptyState, RailPanelShell } from "./RailPanelShell";

export function MemoriesPanel() {
  return (
    <RailPanelShell title="Memories">
      <RailEmptyState
        icon={<Brain className="h-8 w-8" aria-hidden />}
        heading="No memories for this site yet"
        description="Auto-written memories and anything you save with the remember tool will appear here. Manage them in Settings → Memory."
      />
    </RailPanelShell>
  );
}
