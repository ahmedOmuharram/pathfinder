"use client";

import { useState } from "react";
import { toast } from "sonner";
import { CombineOperator, DEFAULT_STREAM_NAME } from "@pathfinder/shared";
import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { computeStepCounts } from "@/lib/api/conversations";
import { useStepCounts } from "@/features/strategy/services/useStepCounts";
import { useWdkUrlFallback } from "@/features/strategy/services/useWdkUrlFallback";
import { useGraphConnections } from "@/features/strategy/graph/hooks/useGraphConnections";
import { useGraphSelection } from "@/features/strategy/graph/hooks/useGraphSelection";
import { useAutoSync } from "@/features/strategy/graph/hooks/useAutoSync";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyGraphNodes } from "@/features/strategy/graph/hooks/useStrategyGraphNodes";
import { useStrategyGraphHandlers } from "@/features/strategy/graph/hooks/useStrategyGraphHandlers";
import { useStrategyGraphLayout } from "@/features/strategy/graph/hooks/useStrategyGraphLayout";

const COMBINE_MISMATCH_ERROR = "Cannot combine steps with different record types.";
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

  // --- Name/description local state ---
  const [nameValue, setNameValue] = useState("");
  const [descriptionValue, setDescriptionValue] = useState("");
  const [detailsCollapsed, setDetailsCollapsed] = useState(false);

  const toggleDetailsCollapsed = () => {
    setDetailsCollapsed((prev) => !prev);
  };

  // --- Store selectors ---
  const draftStrategy = useStrategyStore((state) => state.strategy);
  const updateStep = useStrategyStore((state) => state.updateStep);
  const addStep = useStrategyStore((state) => state.addStep);
  const setStrategyMeta = useStrategyStore((state) => state.setStrategyMeta);
  const applyStepCounts = useStrategyStore((state) => state.applyStepCounts);
  const selectedSite = useSessionStore((state) => state.selectedSite);

  // --- Auto-sync ---
  const { syncStatus, lastSyncError, triggerSync } = useAutoSync({
    strategy,
    siteId,
  });

  // --- Sub-hook: Nodes ---
  const graphNodes = useStrategyGraphNodes({ strategy, siteId, variant });

  // --- Selection ---
  const {
    interactionMode,
    setInteractionMode,
    selectedNodeIds,
    setSelectedNodeIds,
    handleAddToChat,
    handleAddSelectionToChat,
    handleSelectionChange,
  } = useGraphSelection({ strategy, isCompact });

  // --- Connections ---
  const {
    pendingCombine,
    isValidConnection,
    handleConnect,
    handleDeleteEdge,
    handleCombineCreate,
    handleCombineCancel,
    startCombine,
  } = useGraphConnections({
    steps: graphNodes.editableSteps,
    addStep,
    updateStep,
    failCombineMismatch: () => {
      toast.error(COMBINE_MISMATCH_ERROR);
    },
    triggerSync,
  });

  // --- Sub-hook: Handlers ---
  const handlers = useStrategyGraphHandlers({
    strategy,
    isCompact,
    editableSteps: graphNodes.editableSteps,
    selectedStep: graphNodes.selectedStep,
    setSelectedStep: graphNodes.setSelectedStep,
    selectedNodeIds,
    startCombine,
    triggerSync,
  });

  // --- Sub-hook: Layout ---
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
    triggerSync,
  });

  // --- WDK fallback URL ---
  const wdkUrlFallback = useWdkUrlFallback({
    wdkStrategyId: strategy?.wdkStrategyId,
    siteId: strategy?.siteId ?? selectedSite,
  });

  // --- Step counts ---
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

  const draftSyncKey = graphNodes.isDraftView
    ? `${draftStrategy?.name}|${draftStrategy?.description}`
    : null;
  const [prevDraftSyncKey, setPrevDraftSyncKey] = useState(draftSyncKey);
  if (draftSyncKey != null && draftSyncKey !== prevDraftSyncKey) {
    setPrevDraftSyncKey(draftSyncKey);
    setNameValue(draftStrategy?.name ?? DEFAULT_STREAM_NAME);
    setDescriptionValue(draftStrategy?.description ?? "");
  }

  // --- Name/description commit ---
  const handleNameCommit = async () => {
    const name = nameValue.trim();
    if (name === "" || name === draftStrategy?.name) {
      setNameValue(draftStrategy?.name ?? DEFAULT_STREAM_NAME);
      return;
    }
    setStrategyMeta({ name });
    triggerSync();
  };

  const handleDescriptionCommit = async () => {
    const description = descriptionValue.trim();
    if (description === (draftStrategy?.description ?? "")) {
      setDescriptionValue(draftStrategy?.description ?? "");
      return;
    }
    setStrategyMeta({ description });
    triggerSync();
  };

  // --- Wrap updateStep to trigger sync after user edits ---
  const updateStepAndSync = (stepId: string, updates: Partial<Step>) => {
    updateStep(stepId, updates);
    triggerSync();
  };

  return {
    // State
    isCompact,
    nodes: graphNodes.renderNodes,
    edges: graphNodes.edges,
    selectedStep: graphNodes.selectedStep,
    setSelectedStep: graphNodes.setSelectedStep,
    edgeMenu: handlers.edgeMenu,
    setEdgeMenu: handlers.setEdgeMenu,
    orthologModalOpen: handlers.orthologModalOpen,
    setOrthologModalOpen: handlers.setOrthologModalOpen,
    nameValue,
    setNameValue,
    descriptionValue,
    setDescriptionValue,
    detailsCollapsed,
    toggleDetailsCollapsed,
    syncStatus,
    lastSyncError,

    // Selection
    interactionMode,
    setInteractionMode,
    selectedNodeIds,
    handleAddSelectionToChat,
    handleSelectionChange,

    // Connections
    pendingCombine,
    isValidConnection,
    handleConnect,
    handleDeleteEdge,
    handleCombineCreate,
    handleCombineCancel,

    // Actions
    onNodesChange: graphNodes.onNodesChange,
    onEdgesChange: graphNodes.onEdgesChange,
    handleNodesDelete: handlers.handleNodesDelete,
    handleNodeDragStop: layout.handleNodeDragStop,
    handleStartCombineFromSelection: handlers.handleStartCombineFromSelection,
    handleStartOrthologTransformFromSelection:
      handlers.handleStartOrthologTransformFromSelection,
    handleNameCommit,
    handleDescriptionCommit,
    handleOrthologChoose: handlers.handleOrthologChoose,
    handleRelayout: layout.handleRelayout,
    handleMoveStart: layout.handleMoveStart,
    resetViewTracking: layout.resetViewTracking,
    triggerSync,

    // Data
    editableSteps: graphNodes.editableSteps,
    draftStrategy,
    wdkUrlFallback,
    updateStep: updateStepAndSync,
  } as const;
}
