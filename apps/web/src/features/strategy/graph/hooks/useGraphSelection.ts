import { useCallback, useRef, useState } from "react";
import type { Node } from "reactflow";
import type { StrategyWithMeta } from "@/types/strategy";
import { buildNodeSelectionPayload } from "@/features/strategy/graph/utils/nodeSelectionPayload";

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
  const selectedNodeIdsRef = useRef<string[]>([]);

  const buildSelectionPayload = useCallback(
    (nodeIds: string[]) => buildNodeSelectionPayload(strategy, nodeIds),
    [strategy],
  );

  const handleAddToChat = useCallback(
    (stepId: string) => {
      if (!stepId) return;
      if (typeof window === "undefined") return;
      const detail = buildSelectionPayload([stepId]);
      window.dispatchEvent(new CustomEvent("pathfinder:ask-node", { detail }));
    },
    [buildSelectionPayload],
  );

  const handleAddSelectionToChat = useCallback(() => {
    const currentSelection = selectedNodeIdsRef.current;
    if (currentSelection.length === 0) return;
    if (typeof window === "undefined") return;
    const detail = buildSelectionPayload(currentSelection);
    window.dispatchEvent(new CustomEvent("pathfinder:ask-node", { detail }));
  }, [buildSelectionPayload]);

  const handleSelectionChange = useCallback(
    (selectedNodes: Node[]) => {
      if (isCompact) return;
      const nextIds = selectedNodes.map((node) => node.id).sort();
      setSelectedNodeIds((prev) => {
        if (areNodeIdsEqual(prev, nextIds)) return prev;
        selectedNodeIdsRef.current = nextIds;
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
    selectedNodeIdsRef,
    handleAddToChat,
    handleAddSelectionToChat,
    handleSelectionChange,
  };
}
