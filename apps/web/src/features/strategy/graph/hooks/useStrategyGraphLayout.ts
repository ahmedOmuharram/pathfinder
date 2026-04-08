"use client";

import { useState } from "react";
import type { Edge, Node } from "@xyflow/react";
import { useReactFlow } from "@xyflow/react";
import { useEventListener } from "usehooks-ts";
import type { Step, Strategy } from "@pathfinder/shared";
import { useShallow } from "zustand/react/shallow";
import { useStrategyStore } from "@/state/strategy/store";
import { useStrategyHistory } from "@/state/useStrategySelectors";
import { useNodePositionHistory } from "@/features/strategy/graph/hooks/useNodePositionHistory";
import { deserializeStrategyToGraph } from "@/lib/strategyGraph";

interface UseStrategyGraphLayoutOptions {
  strategy: Strategy | null;
  isCompact: boolean;
  nodes: Node[];
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>;
  nodePositions: Map<string, { x: number; y: number }>;
  handleAddToChat: (stepId: string) => void;
  handleOpenDetails: (stepId: string) => void;
  setSelectedNodeIds: (ids: string[]) => void;
  triggerSync: () => void;
}

/**
 * Layout computation, viewport management, relayout triggers,
 * undo/redo for node positions, and graph deserialization side effect.
 */
export function useStrategyGraphLayout(options: UseStrategyGraphLayoutOptions) {
  const {
    strategy,
    isCompact,
    nodes,
    setNodes,
    setEdges,
    nodePositions,
    handleAddToChat,
    handleOpenDetails,
    setSelectedNodeIds,
    triggerSync,
  } = options;

  const [layoutSeed, setLayoutSeed] = useState(0);
  const [userHasMoved, setUserHasMoved] = useState(false);
  const { fitView } = useReactFlow();
  const [prevLayoutSeed, setPrevLayoutSeed] = useState(layoutSeed);
  const [prevStrategyId, setPrevStrategyId] = useState<string | null>(strategy?.id ?? null);

  const { updateStep, strategy: draftStrategy } = useStrategyStore(
    useShallow((s) => ({ updateStep: s.updateStep, strategy: s.strategy })),
  );
  const { undo, redo, canUndo, canRedo } = useStrategyHistory();

  // --- Node position undo/redo ---
  const {
    pushSnapshot,
    reset: resetNodeHistory,
    tryUndo,
    tryRedo,
  } = useNodePositionHistory({ setNodes });

  const currentStrategyId = strategy?.id ?? null;
  if (prevStrategyId !== currentStrategyId) {
    setPrevStrategyId(currentStrategyId);
    setUserHasMoved(false);
    setSelectedNodeIds([]);
  }

  // --- Undo/redo hotkeys ---
  const handleUndoRedoKeyDown = (event: KeyboardEvent) => {
    const target = event.target as HTMLElement | null;
    if (
      target &&
      (target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable)
    ) {
      return;
    }
    if (!(event.ctrlKey || event.metaKey)) return;
    const key = event.key.toLowerCase();
    if (key !== "z" && key !== "y") return;
    event.preventDefault();
    if (key === "y" || event.shiftKey) {
      if (tryRedo()) return;
      if (canRedo()) {
        redo();
        triggerSync();
      }
      return;
    }
    if (tryUndo()) return;
    if (canUndo()) {
      undo();
      triggerSync();
    }
  };
  useEventListener("keydown", handleUndoRedoKeyDown);

  const graphKey = `${strategy?.id}|${draftStrategy?.id}|${layoutSeed}`;
  const [prevGraphKey, setPrevGraphKey] = useState(graphKey);
  if (graphKey !== prevGraphKey) {
    const forceRelayout =
      prevLayoutSeed !== layoutSeed || prevStrategyId !== currentStrategyId;
    setPrevGraphKey(graphKey);
    setPrevLayoutSeed(layoutSeed);

    const { nodes: newNodes, edges: newEdges } = deserializeStrategyToGraph(
      strategy,
      (stepId, operator) => {
        const patch: Partial<Step> = { operator };
        updateStep(stepId, patch);
      },
      handleAddToChat,
      handleOpenDetails,
      undefined,
      {
        existingPositions: nodePositions,
        forceRelayout,
      },
    );
    setNodes(newNodes);
    setEdges(newEdges);
    if (forceRelayout) {
      resetNodeHistory(newNodes);
    }
    if (!isCompact && !userHasMoved && (forceRelayout || newNodes.length > nodes.length)) {
      queueMicrotask(() => void fitView({ padding: 0.3, duration: 300 }));
    }
  }

  const handleNodeDragStop = () => {
    pushSnapshot(nodes);
  };

  const handleRelayout = () => {
    setLayoutSeed((prev) => prev + 1);
  };

  const handleMoveStart = () => {
    setUserHasMoved(true);
  };

  const resetViewTracking = () => {
    setUserHasMoved(false);
    void fitView({ padding: 0.3, duration: 300 });
  };

  return {
    handleNodeDragStop,
    handleRelayout,
    handleMoveStart,
    resetViewTracking,
  } as const;
}
