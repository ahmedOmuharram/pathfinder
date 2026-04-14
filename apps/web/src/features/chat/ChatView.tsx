"use client";

import { useState } from "react";

import { ChatPanel } from "@/features/chat/ChatPanel";
import { CompactStrategyView } from "@/features/strategy/graph/components/CompactStrategyView";
import { GraphEditorModal } from "@/lib/components/GraphEditorModal";
import { useGeneSetExport } from "@/lib/hooks/useGeneSetExport";
import { useStableGraph } from "@/lib/hooks/useStableGraph";
import { useToasts } from "@/lib/hooks/useToasts";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyStore } from "@/state/strategy/store";

export function ChatView({ chatId }: { chatId: string }) {
  const setStrategyId = useSessionStore((s) => s.setStrategyId);
  const currentStrategyId = useSessionStore((s) => s.strategyId);
  const clearStrategy = useStrategyStore((s) => s.clear);
  const strategy = useStrategyStore((s) => s.strategy);
  const selectedSite = useSessionStore((s) => s.selectedSite);

  const { addToast } = useToasts();
  const [graphEditing, setGraphEditing] = useState(false);
  const { exportingGeneSet, handleExportAsGeneSet } = useGeneSetExport();
  const { displayStrategy, hasGraph } = useStableGraph(strategy);

  const [syncedFor, setSyncedFor] = useState<string | null>(null);
  const normalizedChatId = chatId === "" ? null : chatId;
  if (normalizedChatId !== syncedFor) {
    setSyncedFor(normalizedChatId);
    if (currentStrategyId !== normalizedChatId) {
      setStrategyId(normalizedChatId);
      if (normalizedChatId === null) {
        clearStrategy();
      }
    }
  }

  return (
    <div className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-card">
      <div className="min-h-0 flex-1">
        <ChatPanel chatId={chatId} mode="strategy" />
      </div>

      {hasGraph && displayStrategy && (
        <CompactStrategyView
          strategy={displayStrategy}
          onEditGraph={() => setGraphEditing(true)}
          onExportAsGeneSet={(s) => void handleExportAsGeneSet(s)}
          exportingGeneSet={exportingGeneSet}
        />
      )}

      <GraphEditorModal
        open={graphEditing}
        onClose={() => setGraphEditing(false)}
        strategy={displayStrategy ?? strategy}
        siteId={selectedSite}
        onToast={addToast}
      />
    </div>
  );
}
