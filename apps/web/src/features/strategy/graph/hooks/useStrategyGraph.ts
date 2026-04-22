"use client";

import { CombineOperator } from "@pathfinder/shared";
import type { Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { computeStepCounts } from "@/lib/api/conversations";
import { useStepCounts } from "@/features/strategy/services/useStepCounts";
import { useGraphConnections } from "@/features/strategy/graph/hooks/useGraphConnections";
import { useGraphSelection } from "@/features/strategy/graph/hooks/useGraphSelection";
import { useStrategyGraphNodes } from "@/features/strategy/graph/hooks/useStrategyGraphNodes";
import { useStrategyGraphHandlers } from "@/features/strategy/graph/hooks/useStrategyGraphHandlers";
import { useStrategyGraphLayout } from "@/features/strategy/graph/hooks/useStrategyGraphLayout";
import {
  useAddStepMutation,
  useUpdateStepMutation,
  useUpdateStrategyMetaMutation,
} from "@/features/strategy/mutations";

export const COMBINE_OPERATORS = Object.values(CombineOperator);

interface UseStrategyGraphOptions {
  strategy: Strategy | null;
  siteId: string;
  variant?: "full" | "compact";
}

/** Orchestrates all StrategyGraph state, derived values, callbacks, and side effects. */
export function useStrategyGraph(options: UseStrategyGraphOptions) {
  const { strategy, siteId, variant = "full" } = options;
  const isCompact = variant === "compact";

  const draftStrategy = useStrategyStore((state) => state.strategy);
  const applyStepCounts = useStrategyStore((state) => state.applyStepCounts);

  const updateMetaMutation = useUpdateStrategyMetaMutation();
  const addStepMutation = useAddStepMutation();
  const updateStepMutation = useUpdateStepMutation();

  const graphNodes = useStrategyGraphNodes({ strategy, siteId, variant });

  const {
    selectedNodeIds,
    setSelectedNodeIds,
    handleAddToChat,
    handleAddSelectionToChat,
    handleSelectionChange,
  } = useGraphSelection({ strategy, isCompact });

  const {
    isValidConnection,
    handleConnect,
    handleDeleteEdge,
    startCombine,
  } = useGraphConnections({
    steps: graphNodes.editableSteps,
  });

  const handlers = useStrategyGraphHandlers({
    strategy,
    isCompact,
    editableSteps: graphNodes.editableSteps,
    selectedStep: graphNodes.selectedStep,
    setSelectedStep: graphNodes.setSelectedStep,
    selectedNodeIds,
    startCombine,
  });

  const layout = useStrategyGraphLayout({
    strategy,
    isCompact,
    nodes: graphNodes.nodes,
    setNodes: graphNodes.setNodes,
    setEdges: graphNodes.setEdges,
    nodePositions: graphNodes.nodePositions,
    handleAddToChat,
    handleOpenDetails: handlers.handleOpenDetails,
    setSelectedNodeIds,
  });

  useStepCounts({
    siteId,
    plan: graphNodes.graphHasValidationIssues
      ? null
      : (graphNodes.planResult?.plan ?? null),
    planHash: graphNodes.graphHasValidationIssues ? null : graphNodes.planHash,
    stepIds: (draftStrategy?.steps ?? strategy?.steps ?? []).map((step) => step.id),
    applyStepCounts,
    fetchCounts: computeStepCounts,
  });

  const syncStatus: "idle" | "syncing" | "error" =
    addStepMutation.isPending ||
    updateStepMutation.isPending ||
    updateMetaMutation.isPending
      ? "syncing"
      : addStepMutation.isError ||
          updateStepMutation.isError ||
          updateMetaMutation.isError
        ? "error"
        : "idle";

  return {
    isCompact,
    nodes: graphNodes.renderNodes,
    edges: graphNodes.edges,
    selectedStep: graphNodes.selectedStep,
    setSelectedStep: graphNodes.setSelectedStep,
    edgeMenu: handlers.edgeMenu,
    setEdgeMenu: handlers.setEdgeMenu,
    orthologModalOpen: handlers.orthologModalOpen,
    setOrthologModalOpen: handlers.setOrthologModalOpen,
    syncStatus,

    selectedNodeIds,
    handleAddSelectionToChat,
    handleSelectionChange,

    isValidConnection,
    handleConnect,
    handleDeleteEdge,

    onNodesChange: graphNodes.onNodesChange,
    onEdgesChange: graphNodes.onEdgesChange,
    handleNodesDelete: handlers.handleNodesDelete,
    handleNodeDragStop: layout.handleNodeDragStop,
    handleStartCombineFromSelection: handlers.handleStartCombineFromSelection,
    handleStartOrthologTransformFromSelection:
      handlers.handleStartOrthologTransformFromSelection,
    handleOrthologChoose: handlers.handleOrthologChoose,
    handleRelayout: layout.handleRelayout,
    handleMoveStart: layout.handleMoveStart,

    editableSteps: graphNodes.editableSteps,
    combineMismatchGroups: graphNodes.combineMismatchGroups,
    draftStrategy,
    /** Single-step patch — wraps useUpdateStepMutation.mutate. */
    updateStep: (stepId: string, patch: Parameters<typeof updateStepMutation.mutate>[0]["patch"]) =>
      updateStepMutation.mutate({ stepId, patch }),
  } as const;
}
