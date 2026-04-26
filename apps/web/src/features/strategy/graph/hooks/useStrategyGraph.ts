"use client";

import { CombineOperator } from "@pathfinder/shared";
import type { Strategy } from "@pathfinder/shared";
import { useIsMutating } from "@tanstack/react-query";
import { useStrategyStore } from "@/state/strategy/store";
import { computeStepCounts } from "@/lib/api/conversations";
import { PUSH_STRATEGY_MUTATION_KEY } from "@/features/strategy/mutations/usePushStrategyMutation";
import { STEP_PATCH_MUTATION_KEY } from "@/features/strategy/mutations/useUpdateStepMutation";
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
  const conversationId = strategy?.id ?? "";

  const applyStepCounts = useStrategyStore((state) => state.applyStepCounts);

  const updateMetaMutation = useUpdateStrategyMetaMutation(conversationId);
  const addStepMutation = useAddStepMutation(conversationId);
  const updateStepMutation = useUpdateStepMutation(conversationId);

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
    conversationId,
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
    stepIds: (strategy?.steps ?? []).map((step) => step.id),
    applyStepCounts,
    fetchCounts: computeStepCounts,
  });

  const inFlightPushes = useIsMutating({ mutationKey: PUSH_STRATEGY_MUTATION_KEY });
  const inFlightStepPatches = useIsMutating({ mutationKey: STEP_PATCH_MUTATION_KEY });
  const syncStatus: "idle" | "syncing" | "error" =
    inFlightPushes + inFlightStepPatches > 0
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
    updateStep: (stepId: string, patch: Parameters<typeof updateStepMutation.mutate>[0]["patch"]) =>
      updateStepMutation.mutate({ stepId, patch }),
  } as const;
}
