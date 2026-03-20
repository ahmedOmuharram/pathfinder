"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useEventListener } from "usehooks-ts";
import { CombineOperator, DEFAULT_STREAM_NAME } from "@pathfinder/shared";
import type { Strategy } from "@pathfinder/shared";
import { usePrevious } from "@/lib/hooks/usePrevious";
import { useStrategyStore } from "@/state/strategy/store";
import { computeStepCounts } from "@/lib/api/strategies";
import { listSites } from "@/lib/api/sites";
import { useStepCounts } from "@/features/strategy/services/useStepCounts";
import { useWdkUrlFallback } from "@/features/strategy/services/useWdkUrlFallback";
import { useGraphConnections } from "@/features/strategy/graph/hooks/useGraphConnections";
import { useGraphSelection } from "@/features/strategy/graph/hooks/useGraphSelection";
import { useGraphSave } from "@/features/strategy/graph/hooks/useGraphSave";
import { useSessionStore } from "@/state/useSessionStore";
import { useStrategyGraphNodes } from "@/features/strategy/graph/hooks/useStrategyGraphNodes";
import { useStrategyGraphHandlers } from "@/features/strategy/graph/hooks/useStrategyGraphHandlers";
import { useStrategyGraphLayout } from "@/features/strategy/graph/hooks/useStrategyGraphLayout";

const COMBINE_MISMATCH_ERROR = "Cannot combine steps with different record types.";
export const COMBINE_OPERATORS = Object.values(CombineOperator);

interface UseStrategyGraphOptions {
  strategy: Strategy | null;
  siteId: string;
  onToast?: (toast: {
    type: "success" | "error" | "warning" | "info";
    message: string;
  }) => void;
  variant?: "full" | "compact";
}

/** Orchestrates all StrategyGraph state, derived values, callbacks, and side effects. */
export function useStrategyGraph(options: UseStrategyGraphOptions) {
  const { strategy, siteId, onToast, variant = "full" } = options;
  const isCompact = variant === "compact";

  // --- Name/description local state ---
  const [nameValue, setNameValue] = useState("");
  const [descriptionValue, setDescriptionValue] = useState("");
  const [detailsCollapsed, setDetailsCollapsed] = useState(false);

  const toggleDetailsCollapsed = useCallback(() => {
    setDetailsCollapsed((prev) => !prev);
  }, []);

  // --- Store selectors ---
  const draftStrategy = useStrategyStore((state) => state.strategy);
  const updateStep = useStrategyStore((state) => state.updateStep);
  const addStep = useStrategyStore((state) => state.addStep);
  const buildPlan = useStrategyStore((state) => state.buildPlan);
  const setStrategyMeta = useStrategyStore((state) => state.setStrategyMeta);
  const setStepCounts = useStrategyStore((state) => state.setStepCounts);
  const selectedSite = useSessionStore((state) => state.selectedSite);

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
      onToast?.({ type: "error", message: COMBINE_MISMATCH_ERROR });
    },
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
  });

  // --- Sub-hook: Layout ---
  const layout = useStrategyGraphLayout({
    strategy,
    isCompact,
    nodes: graphNodes.nodes,
    setNodes: graphNodes.setNodes,
    setEdges: graphNodes.setEdges,
    nodePositionsRef: graphNodes.nodePositionsRef,
    dirtyStepIds: graphNodes.dirtyStepIds,
    isUnsaved: graphNodes.isUnsaved,
    handleAddToChat,
    handleOpenDetails: handlers.handleOpenDetails,
    setSelectedNodeIds,
  });

  // --- WDK fallback URL ---
  const wdkUrlFallback = useWdkUrlFallback({
    wdkStrategyId: strategy?.wdkStrategyId,
    siteId: strategy?.siteId ?? selectedSite,
    listSites,
  });

  // --- Step counts ---
  useStepCounts({
    siteId,
    plan: graphNodes.graphHasValidationIssues
      ? null
      : (graphNodes.planResult?.plan ?? null),
    planHash: graphNodes.graphHasValidationIssues ? null : graphNodes.planHash,
    stepIds: (draftStrategy?.steps ?? strategy?.steps ?? []).map((step) => step.id),
    setStepCounts,
    fetchCounts: computeStepCounts,
  });

  // --- Save ---
  const graphSaveArgs: Parameters<typeof useGraphSave>[0] = {
    strategy,
    draftStrategy,
    buildPlan,
    combineMismatchGroups: graphNodes.combineMismatchGroups,
    setStrategyMeta,
    buildStepSignature: graphNodes.buildStepSignature,
    setLastSavedSteps: graphNodes.setLastSavedSteps,
    setLastSavedStepsVersion: graphNodes.setLastSavedStepsVersion,
    validateSearchSteps: graphNodes.validateSearchSteps,
    nameValue,
    setNameValue,
    descriptionValue,
  };
  if (onToast != null) {
    graphSaveArgs.onToast = onToast;
  }
  const { isSaving, canSave, handleSave } = useGraphSave(graphSaveArgs);

  const saveDisabledReason = useMemo(() => {
    if (canSave && !isSaving && !graphNodes.graphHasValidationIssues) return undefined;
    if (isSaving) return "Saving...";
    if (draftStrategy == null) return "No draft strategy loaded.";
    if (strategy?.id !== draftStrategy.id) {
      return "Open the active draft to save.";
    }
    if (graphNodes.graphHasValidationIssues) {
      return "Cannot save: fix the validation errors highlighted in the graph.";
    }
    if (!buildPlan()) {
      return "Cannot save: strategy must have a single final output step. Add a final combine step (e.g., UNION) to produce one output.";
    }
    return "Save is currently unavailable.";
  }, [
    canSave,
    isSaving,
    draftStrategy,
    strategy,
    buildPlan,
    graphNodes.graphHasValidationIssues,
  ]);

  // --- Before-unload guard ---
  const handleBeforeUnload = useCallback(
    (event: BeforeUnloadEvent) => {
      if (!graphNodes.isUnsaved) return;
      event.preventDefault();
      event.returnValue = "";
    },
    [graphNodes.isUnsaved],
  );
  useEventListener("beforeunload", handleBeforeUnload);

  // --- Draft details sync (defer setState to avoid synchronous setState in effect) ---
  useEffect(() => {
    if (!graphNodes.isDraftView) return;
    const name = draftStrategy?.name ?? DEFAULT_STREAM_NAME;
    const description = draftStrategy?.description ?? "";
    queueMicrotask(() => {
      setNameValue(name);
      setDescriptionValue(description);
    });
  }, [
    graphNodes.isDraftView,
    draftStrategy?.name,
    draftStrategy?.description,
    setNameValue,
    setDescriptionValue,
  ]);

  // --- Saved snapshot sync ---
  const snapshotId = strategy?.id ?? null;
  const prevSnapshotId = usePrevious(snapshotId);
  useEffect(() => {
    if (snapshotId == null || snapshotId === "" || snapshotId === prevSnapshotId)
      return;
    if (strategy?.steps) {
      graphNodes.setLastSavedSteps(
        new Map(
          strategy.steps.map((step) => [step.id, graphNodes.buildStepSignature(step)]),
        ),
      );
      graphNodes.setLastSavedStepsVersion((v) => v + 1);
    }
  }, [snapshotId, prevSnapshotId, strategy?.steps, graphNodes]);

  // --- Name/description commit ---
  const handleNameCommit = useCallback(async () => {
    const name = nameValue.trim();
    if (name === "" || name === draftStrategy?.name) {
      setNameValue(draftStrategy?.name ?? DEFAULT_STREAM_NAME);
      return;
    }
    setStrategyMeta({ name });
  }, [nameValue, draftStrategy?.name, setNameValue, setStrategyMeta]);

  const handleDescriptionCommit = useCallback(async () => {
    const description = descriptionValue.trim();
    if (description === (draftStrategy?.description ?? "")) {
      setDescriptionValue(draftStrategy?.description ?? "");
      return;
    }
    setStrategyMeta({ description });
  }, [
    descriptionValue,
    draftStrategy?.description,
    setDescriptionValue,
    setStrategyMeta,
  ]);

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
    isUnsaved: graphNodes.isUnsaved,
    isSaving,
    canSave,
    saveDisabledReason,

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
    handleSave,
    handleNameCommit,
    handleDescriptionCommit,
    handleOrthologChoose: handlers.handleOrthologChoose,
    handleRelayout: layout.handleRelayout,
    handleMoveStart: layout.handleMoveStart,
    handleInit: layout.handleInit,

    // Data
    editableSteps: graphNodes.editableSteps,
    draftStrategy,
    wdkUrlFallback,
    updateStep,
  } as const;
}
