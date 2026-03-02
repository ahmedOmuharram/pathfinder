"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Node, ReactFlowInstance } from "reactflow";
import { usePrevious } from "@/lib/hooks/usePrevious";
import type { StrategyStep, StrategyWithMeta } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/useStrategyStore";
import { useAutoFitView } from "@/features/strategy/graph/hooks/useAutoFitView";
import { useNodePositionHistory } from "@/features/strategy/graph/hooks/useNodePositionHistory";
import { useUndoRedoHotkeys } from "@/features/strategy/graph/hooks/useUndoRedoHotkeys";
import { useResetGraphUiOnStrategyChange } from "@/features/strategy/graph/hooks/useResetGraphUiOnStrategyChange";
import { deserializeStrategyToGraph } from "@/lib/strategyGraph";

interface UseStrategyGraphLayoutOptions {
  strategy: StrategyWithMeta | null;
  isCompact: boolean;
  nodes: Node[];
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>;
  setEdges: React.Dispatch<React.SetStateAction<import("reactflow").Edge[]>>;
  nodePositionsRef: React.MutableRefObject<Map<string, { x: number; y: number }>>;
  dirtyStepIds: Set<string>;
  isUnsaved: boolean;
  handleAddToChat: (stepId: string) => void;
  handleOpenDetails: (stepId: string) => void;
  setSelectedNodeIds: (ids: string[]) => void;
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
    nodePositionsRef,
    dirtyStepIds,
    isUnsaved,
    handleAddToChat,
    handleOpenDetails,
    setSelectedNodeIds,
  } = options;

  const [layoutSeed, setLayoutSeed] = useState(0);
  const [userHasMoved, setUserHasMoved] = useState(false);
  const reactFlowInstanceRef = useRef<ReactFlowInstance | null>(null);
  const prevLayoutSeed = usePrevious(layoutSeed);
  const prevStrategyId = usePrevious(strategy?.id ?? null);

  const updateStep = useStrategyStore((state) => state.updateStep);
  const undo = useStrategyStore((state) => state.undo);
  const redo = useStrategyStore((state) => state.redo);
  const canUndo = useStrategyStore((state) => state.canUndo);
  const canRedo = useStrategyStore((state) => state.canRedo);
  const draftStrategy = useStrategyStore((state) => state.strategy);

  const autoFit = useAutoFitView({
    enabled: !isCompact,
    nodeCount: nodes.length,
    userHasMoved,
    fitView: () =>
      reactFlowInstanceRef.current?.fitView({ padding: 0.3, duration: 300 }),
  });

  const {
    pushSnapshot,
    reset: resetNodeHistory,
    tryUndo,
    tryRedo,
  } = useNodePositionHistory({ setNodes });

  useResetGraphUiOnStrategyChange({
    strategyId: strategy?.id,
    setUserHasMoved,
    autoFitReset: autoFit.reset,
    setSelectedNodeIds,
  });

  useUndoRedoHotkeys({
    enabled: true,
    tryUndoLocal: tryUndo,
    tryRedoLocal: tryRedo,
    canUndoGlobal: canUndo,
    canRedoGlobal: canRedo,
    undoGlobal: undo,
    redoGlobal: redo,
  });

  // Deserialize strategy to graph nodes/edges
  useEffect(() => {
    const forceRelayout =
      prevLayoutSeed !== layoutSeed || prevStrategyId !== (strategy?.id || null);

    const { nodes: newNodes, edges: newEdges } = deserializeStrategyToGraph(
      strategy,
      (stepId, operator) => {
        updateStep(stepId, { operator: operator as StrategyStep["operator"] });
      },
      handleAddToChat,
      handleOpenDetails,
      isUnsaved ? dirtyStepIds : undefined,
      {
        existingPositions: nodePositionsRef.current,
        forceRelayout,
      },
    );
    setNodes(newNodes);
    setEdges(newEdges);
    if (forceRelayout) {
      resetNodeHistory(newNodes);
    }
  }, [
    strategy,
    setNodes,
    setEdges,
    updateStep,
    draftStrategy?.id,
    handleAddToChat,
    handleOpenDetails,
    layoutSeed,
    prevLayoutSeed,
    prevStrategyId,
    resetNodeHistory,
    dirtyStepIds,
    isUnsaved,
    nodePositionsRef,
  ]);

  const handleNodeDragStop = useCallback(() => {
    pushSnapshot(nodes);
  }, [nodes, pushSnapshot]);

  const handleRelayout = useCallback(() => {
    setLayoutSeed((prev) => prev + 1);
  }, []);

  const handleMoveStart = useCallback(() => {
    setUserHasMoved(true);
  }, []);

  const handleInit = useCallback((instance: ReactFlowInstance) => {
    reactFlowInstanceRef.current = instance;
  }, []);

  return {
    handleNodeDragStop,
    handleRelayout,
    handleMoveStart,
    handleInit,
  } as const;
}
