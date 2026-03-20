"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Edge, Node, ReactFlowInstance } from "reactflow";
import { useEventListener } from "usehooks-ts";
import { usePrevious } from "@/lib/hooks/usePrevious";
import type { Step, Strategy } from "@pathfinder/shared";
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
  nodePositionsRef: React.RefObject<Map<string, { x: number; y: number }>>;
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
  const { undo, redo, canUndo, canRedo } = useStrategyHistory();
  const draftStrategy = useStrategyStore((state) => state.strategy);

  // --- Auto-fit viewport when nodes are added ---
  const prevNodeCount = usePrevious(nodes.length);
  const autoFitResetRef = useRef(false);
  const [autoFitTrigger, setAutoFitTrigger] = useState(0);

  useEffect(() => {
    if (isCompact) return;
    const prev = autoFitResetRef.current ? 0 : (prevNodeCount ?? 0);
    if (autoFitResetRef.current) autoFitResetRef.current = false;
    if (nodes.length > prev && !userHasMoved) {
      requestAnimationFrame(() =>
        reactFlowInstanceRef.current?.fitView({ padding: 0.3, duration: 300 }),
      );
    }
  }, [isCompact, nodes.length, prevNodeCount, userHasMoved, autoFitTrigger]);

  const resetAutoFit = useCallback(() => {
    autoFitResetRef.current = true;
    setAutoFitTrigger((t) => t + 1);
  }, []);

  // --- Node position undo/redo ---
  const {
    pushSnapshot,
    reset: resetNodeHistory,
    tryUndo,
    tryRedo,
  } = useNodePositionHistory({ setNodes });

  // --- Reset UI on strategy change (defer setState to avoid synchronous setState in effect) ---
  useEffect(() => {
    if (prevStrategyId === undefined) return;
    if (prevStrategyId === (strategy?.id ?? null)) return;
    queueMicrotask(() => {
      setUserHasMoved(false);
      resetAutoFit();
      setSelectedNodeIds([]);
    });
  }, [strategy?.id, prevStrategyId, resetAutoFit, setSelectedNodeIds]);

  // --- Undo/redo hotkeys ---
  const handleUndoRedoKeyDown = useCallback(
    (event: KeyboardEvent) => {
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
        if (canRedo()) redo();
        return;
      }
      if (tryUndo()) return;
      if (canUndo()) undo();
    },
    [tryUndo, tryRedo, canUndo, canRedo, undo, redo],
  );
  useEventListener("keydown", handleUndoRedoKeyDown);

  // Deserialize strategy to graph nodes/edges
  useEffect(() => {
    const forceRelayout =
      prevLayoutSeed !== layoutSeed || prevStrategyId !== (strategy?.id ?? null);

    const { nodes: newNodes, edges: newEdges } = deserializeStrategyToGraph(
      strategy,
      (stepId, operator) => {
        const patch: Partial<Step> = { operator };
        updateStep(stepId, patch);
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
