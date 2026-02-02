import { useEffect } from "react";

export function useConsumePendingAskNode(args: {
  enabled: boolean;
  pendingAskNode: Record<string, unknown> | null;
  setDraftSelection: (value: Record<string, unknown> | null) => void;
  onConsumeAskNode?: () => void;
}) {
  const { enabled, pendingAskNode, setDraftSelection, onConsumeAskNode } = args;

  useEffect(() => {
    if (!enabled) return;
    if (!pendingAskNode) return;
    setDraftSelection(pendingAskNode);
    onConsumeAskNode?.();
  }, [enabled, pendingAskNode, setDraftSelection, onConsumeAskNode]);
}

