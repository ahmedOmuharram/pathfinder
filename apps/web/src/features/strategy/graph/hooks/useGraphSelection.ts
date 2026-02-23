import { useCallback, useState } from "react";
import type { Node } from "reactflow";
import type { StrategyWithMeta } from "@/features/strategy/types";
import { buildNodeSelectionPayload } from "@/features/strategy/graph/utils/nodeSelectionPayload";
import { useSessionStore } from "@/state/useSessionStore";

interface UseGraphSelectionArgs {
  strategy: StrategyWithMeta | null;
  isCompact: boolean;
}

const areNodeIdsEqual = (a: string[], b: string[]) => {
  if (a.length !== b.length) return false;
  return a.every((value, index) => value === b[index]);
};

export function useGraphSelection({ strategy, isCompact }: UseGraphSelectionArgs) {
  const [interactionMode, setInteractionMode] = useState<"select" | "pan">("pan");
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const setPendingAskNode = useSessionStore((s) => s.setPendingAskNode);

  const buildSelectionPayload = useCallback(
    (nodeIds: string[]) => buildNodeSelectionPayload(strategy, nodeIds),
    [strategy],
  );

  const handleAddToChat = useCallback(
    (stepId: string) => {
      if (!stepId) return;
      const detail = buildSelectionPayload([stepId]);
      setPendingAskNode(detail);
    },
    [buildSelectionPayload, setPendingAskNode],
  );

  const handleAddSelectionToChat = useCallback(() => {
    setSelectedNodeIds((currentSelection) => {
      if (currentSelection.length > 0) {
        const detail = buildSelectionPayload(currentSelection);
        setPendingAskNode(detail);
      }
      return currentSelection;
    });
  }, [buildSelectionPayload, setPendingAskNode]);

  const handleSelectionChange = useCallback(
    (selectedNodes: Node[]) => {
      if (isCompact) return;
      const nextIds = selectedNodes.map((node) => node.id).sort();
      setSelectedNodeIds((prev) => {
        if (areNodeIdsEqual(prev, nextIds)) return prev;
        return nextIds;
      });
    },
    [isCompact],
  );

  return {
    interactionMode,
    setInteractionMode,
    selectedNodeIds,
    setSelectedNodeIds,
    handleAddToChat,
    handleAddSelectionToChat,
    handleSelectionChange,
  };
}
