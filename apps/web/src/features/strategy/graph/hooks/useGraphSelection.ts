import { useState } from "react";
import type { Node } from "@xyflow/react";
import type { Strategy } from "@pathfinder/shared";
import { buildNodeSelectionPayload } from "@/features/strategy/graph/utils/nodeSelectionPayload";
import { useSessionStore } from "@/state/useSessionStore";

interface UseGraphSelectionArgs {
  strategy: Strategy | null;
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

  const buildSelectionPayload = (nodeIds: string[]) => buildNodeSelectionPayload(strategy, nodeIds);

  const handleAddToChat = (stepId: string) => {
    if (!stepId) return;
    const detail = buildSelectionPayload([stepId]);
    setPendingAskNode(detail);
  };

  const handleAddSelectionToChat = () => {
    setSelectedNodeIds((currentSelection) => {
      if (currentSelection.length > 0) {
        const detail = buildSelectionPayload(currentSelection);
        setPendingAskNode(detail);
      }
      return currentSelection;
    });
  };

  const handleSelectionChange = (selectedNodes: Node[]) => {
    if (isCompact) return;
    const nextIds = selectedNodes.map((node) => node.id).sort();
    setSelectedNodeIds((prev) => {
      if (areNodeIdsEqual(prev, nextIds)) return prev;
      return nextIds;
    });
  };

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
