import { useState } from "react";
import type { NodeSelection } from "@/lib/types/nodeSelection";

export function useConsumePendingAskNode(args: {
  enabled: boolean;
  pendingAskNode: NodeSelection | null;
  setDraftSelection: (value: NodeSelection | null) => void;
  onConsumeAskNode?: () => void;
}) {
  const { enabled, pendingAskNode, setDraftSelection, onConsumeAskNode } = args;

  const [consumed, setConsumed] = useState<NodeSelection | null>(null);
  if (enabled && pendingAskNode && pendingAskNode !== consumed) {
    setConsumed(pendingAskNode);
    setDraftSelection(pendingAskNode);
    onConsumeAskNode?.();
  }
}
