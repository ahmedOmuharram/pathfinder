"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CombineOperator } from "@pathfinder/shared";
import { Node, useNodesState, useEdgesState, type ReactFlowInstance } from "reactflow";
import "reactflow/dist/style.css";
import type { StrategyStep, StrategyWithMeta } from "@/types/strategy";
import { StepNode } from "@/features/strategy/graph/components/StepNode";
import { useStrategyStore } from "@/state/useStrategyStore";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { StepEditor } from "@/features/strategy/editor/StepEditor";
import { computeStepCounts, listSites } from "@/lib/api/client";
import { validateStepsForSave } from "@/features/strategy/validation/save";
import { useStepCounts } from "@/features/strategy/services/useStepCounts";
import { useWdkUrlFallback } from "@/features/strategy/services/useWdkUrlFallback";
import { useSaveValidation } from "@/features/strategy/validation/useSaveValidation";
import { useAutoFitView } from "@/features/strategy/graph/hooks/useAutoFitView";
import { useNodePositionHistory } from "@/features/strategy/graph/hooks/useNodePositionHistory";
import { useUndoRedoHotkeys } from "@/features/strategy/graph/hooks/useUndoRedoHotkeys";
import { useWarningGroupNodes } from "@/features/strategy/graph/hooks/useWarningGroupNodes";
import { useGraphCombine } from "@/features/strategy/graph/hooks/useGraphCombine";
import { useGraphSelection } from "@/features/strategy/graph/hooks/useGraphSelection";
import { useGraphSave } from "@/features/strategy/graph/hooks/useGraphSave";
import {
  WarningGroupNode,
  WarningIconNode,
} from "@/features/strategy/graph/components/WarningNodes";
import { EmptyGraphState } from "@/features/strategy/graph/components/EmptyGraphState";
import { CombineStepModal } from "@/features/strategy/graph/components/CombineStepModal";
import { StrategyGraphLayout } from "@/features/strategy/graph/components/StrategyGraphLayout";
import { useBeforeUnloadUnsaved } from "@/features/strategy/graph/hooks/useBeforeUnloadUnsaved";
import { useResetGraphUiOnStrategyChange } from "@/features/strategy/graph/hooks/useResetGraphUiOnStrategyChange";
import { useDraftDetailsInputs } from "@/features/strategy/graph/hooks/useDraftDetailsInputs";
import { useSavedSnapshotSync } from "@/features/strategy/graph/hooks/useSavedSnapshotSync";
import { useMarkUnsavedNodes } from "@/features/strategy/graph/hooks/useMarkUnsavedNodes";
import { useSessionStore } from "@/state/useSessionStore";
import {
  deserializeStrategyToGraph,
  getCombineMismatchGroups,
} from "@/features/strategy/domain/graph";

interface StrategyGraphProps {
  strategy: StrategyWithMeta | null;
  siteId: string;
  onReset?: () => void;
  onPush?: () => void;
  canPush?: boolean;
  isPushing?: boolean;
  pushLabel?: string;
  pushDisabledReason?: string;
  onToast?: (toast: { type: "success" | "error" | "warning" | "info"; message: string }) => void;
  variant?: "full" | "compact";
}

const NODE_TYPES = {
  step: StepNode,
  warningGroup: WarningGroupNode,
  warningIcon: WarningIconNode,
};
const FIT_VIEW_OPTIONS = { padding: 0.3 } as const;
const SNAP_GRID: [number, number] = [28, 28];
const COMBINE_OPERATORS = Object.values(CombineOperator);

const DEFAULT_NODE_WIDTH = 224;
const DEFAULT_NODE_HEIGHT = 112;
const COMBINE_MISMATCH_ERROR = "Cannot combine steps with different record types.";

export function StrategyGraph(props: StrategyGraphProps) {
  const {
    strategy,
    siteId,
    onPush,
    canPush = false,
    isPushing = false,
    pushLabel = "Push",
    pushDisabledReason,
    onToast,
    variant = "full",
  } = props;
  const isCompact = variant === "compact";
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [, setSaveError] = useState<string | null>(null);
  const [, setLastSavedPlanHash] = useState<string | null>(null);
  const [lastSavedStepsVersion, setLastSavedStepsVersion] = useState(0);
  const [nameValue, setNameValue] = useState("");
  const [descriptionValue, setDescriptionValue] = useState("");
  const [selectedStep, setSelectedStep] = useState<StrategyStep | null>(null);
  const [userHasMoved, setUserHasMoved] = useState(false);
  const lastSnapshotIdRef = useRef<string | null>(null);
  const lastSavedStepsRef = useRef<Map<string, string>>(new Map());
  const nodeTypes = useRef(NODE_TYPES).current;
  const [layoutSeed, setLayoutSeed] = useState(0);
  const [detailsCollapsed, setDetailsCollapsed] = useState(false);
  const updateStep = useStrategyStore((state) => state.updateStep);
  const addStep = useStrategyStore((state) => state.addStep);
  const removeStep = useStrategyStore((state) => state.removeStep);
  const setStepValidationErrors = useStrategyStore(
    (state) => state.setStepValidationErrors
  );
  const selectedSite = useSessionStore((state) => state.selectedSite);
  const wdkUrlFallback = useWdkUrlFallback({
    wdkStrategyId: strategy?.wdkStrategyId,
    siteId: strategy?.siteId || selectedSite,
    listSites,
  });
  const setGraphValidationStatus = useStrategyListStore(
    (state) => state.setGraphValidationStatus
  );
  const undo = useStrategyStore((state) => state.undo);
  const redo = useStrategyStore((state) => state.redo);
  const canUndo = useStrategyStore((state) => state.canUndo);
  const canRedo = useStrategyStore((state) => state.canRedo);
  const buildPlan = useStrategyStore((state) => state.buildPlan);
  const setStrategyMeta = useStrategyStore((state) => state.setStrategyMeta);
  const draftStrategy = useStrategyStore((state) => state.strategy);
  const setStepCounts = useStrategyStore((state) => state.setStepCounts);
  const reactFlowInstanceRef = useRef<ReactFlowInstance | null>(null);
  const combineMismatchGroups = useMemo(() => {
    const steps = draftStrategy?.steps || strategy?.steps || [];
    return getCombineMismatchGroups(steps);
  }, [draftStrategy?.steps, strategy?.steps]);
  const warningGroupNodes = useWarningGroupNodes({
    nodes,
    groups: combineMismatchGroups,
    defaultNodeWidth: DEFAULT_NODE_WIDTH,
    defaultNodeHeight: DEFAULT_NODE_HEIGHT,
  });
  const renderNodes = useMemo(
    () => (warningGroupNodes.length > 0 ? [...warningGroupNodes, ...nodes] : nodes),
    [warningGroupNodes, nodes]
  );
  // Update nodes and edges when strategy changes
  const buildStepSignature = useCallback((step: StrategyStep) => {
    return JSON.stringify({
      type: step.type,
      displayName: step.displayName,
      searchName: step.searchName,
      transformName: step.transformName,
      operator: step.operator,
      parameters: step.parameters ?? {},
      primaryInputStepId: step.primaryInputStepId,
      secondaryInputStepId: step.secondaryInputStepId,
      recordType: step.recordType,
    });
  }, []);

  const toggleDetailsCollapsed = useCallback(() => {
    setDetailsCollapsed((prev) => !prev);
  }, []);

  const {
    interactionMode,
    setInteractionMode,
    selectedNodeIds,
    setSelectedNodeIds,
    selectedNodeIdsRef,
    handleAddToChat,
    handleAddSelectionToChat,
    handleSelectionChange,
  } = useGraphSelection({ strategy, isCompact });

  const { pendingCombine, handleConnect, handleCombineCreate, handleCombineCancel } =
    useGraphCombine({
      steps: strategy?.steps || [],
      addStep,
      failCombineMismatch: () => {
        setSaveError(COMBINE_MISMATCH_ERROR);
        onToast?.({ type: "error", message: COMBINE_MISMATCH_ERROR });
      },
    });

  const handleNodesDelete = useCallback(
    (deletedNodes: Node[]) => {
      if (isCompact || deletedNodes.length === 0) return;
      const stepsList = draftStrategy?.steps || [];
      if (stepsList.length === 0) return;
      const stepsMap = new Map(stepsList.map((step) => [step.id, step]));
      const toRemove = new Set(
        deletedNodes.map((node) => node.id).filter((id) => stepsMap.has(id))
      );
      if (toRemove.size === 0) return;
      let changed = true;
      while (changed) {
        changed = false;
        for (const step of stepsList) {
          if (toRemove.has(step.id)) continue;
          if (
            step.type === "transform" &&
            step.primaryInputStepId &&
            toRemove.has(step.primaryInputStepId)
          ) {
            toRemove.add(step.id);
            changed = true;
          }
          if (
            step.type === "combine" &&
            ((step.primaryInputStepId && toRemove.has(step.primaryInputStepId)) ||
              (step.secondaryInputStepId &&
                toRemove.has(step.secondaryInputStepId)))
          ) {
            toRemove.add(step.id);
            changed = true;
          }
        }
      }
      for (const stepId of toRemove) {
        removeStep(stepId);
      }
      if (selectedStep && toRemove.has(selectedStep.id)) {
        setSelectedStep(null);
      }
    },
    [draftStrategy?.steps, isCompact, removeStep, selectedStep]
  );

  const autoFit = useAutoFitView({
    enabled: !isCompact,
    nodeCount: nodes.length,
    userHasMoved,
    fitView: () => reactFlowInstanceRef.current?.fitView({ padding: 0.3, duration: 300 }),
  });

  const { pushSnapshot, reset: resetNodeHistory, tryUndo, tryRedo } =
    useNodePositionHistory({ setNodes });

  useResetGraphUiOnStrategyChange({
    strategyId: strategy?.id,
    setUserHasMoved,
    autoFitReset: autoFit.reset,
    setSelectedNodeIds,
    selectedNodeIdsRef,
  });

  const isDraftView = !!draftStrategy && strategy?.id === draftStrategy.id;
  const planResult = buildPlan();
  const planHash = planResult ? JSON.stringify(planResult.plan) : null;
  const dirtyStepIds = useMemo(() => {
    // This is a bump counter used to invalidate the memo when a saved snapshot is observed.
    void lastSavedStepsVersion;
    const dirty = new Set<string>();
    const steps = strategy?.steps || [];
    if (steps.length === 0) return dirty;
    const savedSteps = lastSavedStepsRef.current;
    for (const step of steps) {
      const signature = buildStepSignature(step);
      if (!savedSteps.has(step.id) || savedSteps.get(step.id) !== signature) {
        dirty.add(step.id);
      }
    }
    return dirty;
  }, [strategy?.steps, lastSavedStepsVersion, buildStepSignature]);
  const dirtyStepIdsKey = useMemo(
    () => Array.from(dirtyStepIds).sort().join("|"),
    [dirtyStepIds]
  );
  const isUnsaved = dirtyStepIds.size > 0;

  const validateSearchSteps = useCallback(async () => {
    const steps = draftStrategy?.steps || [];
    if (steps.length === 0) return true;
    const { errorsByStepId, hasErrors: hasFieldErrors } = await validateStepsForSave({
      siteId,
      steps,
      strategy,
    });
    setStepValidationErrors(errorsByStepId);
    const hasErrors = hasFieldErrors || combineMismatchGroups.length > 0;
    const graphId = draftStrategy?.id || strategy?.id;
    if (graphId) {
      setGraphValidationStatus(graphId, hasErrors);
    }
    return !hasErrors;
  }, [
    draftStrategy?.steps,
    combineMismatchGroups,
    setStepValidationErrors,
    setGraphValidationStatus,
    siteId,
    strategy,
    draftStrategy?.id,
  ]);

  useStepCounts({
    siteId,
    plan: planResult?.plan ?? null,
    planHash,
    stepIds: (draftStrategy?.steps || strategy?.steps || []).map((step) => step.id),
    setStepCounts,
    fetchCounts: computeStepCounts,
  });

  useSaveValidation({
    steps: draftStrategy?.steps || [],
    buildStepSignature,
    validate: validateSearchSteps,
    strategy,
  });

  const { isSaving, canSave, handleSave, handlePush } = useGraphSave({
    strategy,
    draftStrategy,
    buildPlan,
    combineMismatchGroups,
    onToast,
    onPush,
    setStrategyMeta,
    buildStepSignature,
    lastSavedStepsRef,
    setLastSavedStepsVersion,
    setLastSavedPlanHash,
    validateSearchSteps,
    nameValue,
    setNameValue,
    descriptionValue,
  });

  const handleNodeDragStop = useCallback(() => {
    pushSnapshot(nodes);
  }, [nodes, pushSnapshot]);

  useUndoRedoHotkeys({
    enabled: true,
    tryUndoLocal: tryUndo,
    tryRedoLocal: tryRedo,
    canUndoGlobal: canUndo,
    canRedoGlobal: canRedo,
    undoGlobal: undo,
    redoGlobal: redo,
  });

  const handleOpenDetails = useCallback(
    (stepId: string) => {
      const step = (strategy?.steps || []).find((item) => item.id === stepId);
      if (step) {
        setSelectedStep(step);
      }
    },
    [strategy?.steps]
  );

  useEffect(() => {
    const { nodes: newNodes, edges: newEdges } = deserializeStrategyToGraph(
      strategy,
      (stepId, operator) => {
        updateStep(stepId, { operator: operator as StrategyStep["operator"] });
      },
      handleAddToChat,
      handleOpenDetails,
      isUnsaved ? dirtyStepIds : undefined
    );
    setNodes(newNodes);
    setEdges(newEdges);
    resetNodeHistory(newNodes);
  }, [
    strategy,
    setNodes,
    setEdges,
    updateStep,
    draftStrategy?.id,
    handleAddToChat,
    handleOpenDetails,
    layoutSeed,
    resetNodeHistory,
    dirtyStepIds,
    isUnsaved,
  ]);

  useMarkUnsavedNodes({ dirtyStepIds, dirtyKey: dirtyStepIdsKey, setNodes });

  useBeforeUnloadUnsaved(isUnsaved);

  useDraftDetailsInputs({
    isDraftView,
    draftName: draftStrategy?.name,
    draftDescription: draftStrategy?.description,
    setNameValue,
    setDescriptionValue,
  });

  useSavedSnapshotSync({
    strategy,
    planHash,
    lastSnapshotIdRef,
    setLastSavedPlanHash,
    lastSavedStepsRef,
    buildStepSignature,
    bumpLastSavedStepsVersion: () => setLastSavedStepsVersion((v) => v + 1),
  });

  const handleNameCommit = async () => {
    const name = nameValue.trim();
    if (!name || name === draftStrategy?.name) {
      setNameValue(draftStrategy?.name || "Draft Strategy");
      return;
    }
    setStrategyMeta({ name });
  };

  const handleDescriptionCommit = async () => {
    const description = descriptionValue.trim();
    if (description === (draftStrategy?.description || "")) {
      setDescriptionValue(draftStrategy?.description || "");
      return;
    }
    setStrategyMeta({ description });
  };

  if (!strategy || strategy.steps.length === 0) {
    return <EmptyGraphState isCompact={isCompact} />;
  }

  return (
    <div className="flex h-full w-full flex-col">
      <StrategyGraphLayout
        isCompact={isCompact}
        detailsCollapsed={detailsCollapsed}
        onToggleCollapsed={toggleDetailsCollapsed}
        nameValue={nameValue}
        onNameChange={setNameValue}
        onNameCommit={() => void handleNameCommit()}
        descriptionValue={descriptionValue}
        onDescriptionChange={setDescriptionValue}
        onDescriptionCommit={() => void handleDescriptionCommit()}
        wdkStrategyId={strategy?.wdkStrategyId ?? undefined}
        wdkUrl={strategy?.wdkUrl}
        wdkUrlFallback={wdkUrlFallback}
        interactionMode={interactionMode}
        onSetInteractionMode={setInteractionMode}
        onRelayout={() => setLayoutSeed((prev) => prev + 1)}
        onAddSelectionToChat={handleAddSelectionToChat}
        canAddSelectionToChat={selectedNodeIds.length > 0}
        showPush={!!onPush}
        onPush={() => void handlePush()}
        canPush={canPush}
        isPushing={isPushing}
        pushLabel={pushLabel}
        pushDisabledReason={pushDisabledReason}
        canSave={canSave && !isSaving}
        onSave={() => void handleSave()}
        isSaving={isSaving}
        isUnsaved={isUnsaved}
        nodes={renderNodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodesDelete={handleNodesDelete}
        onNodeDragStop={handleNodeDragStop}
        onConnect={handleConnect}
        nodeTypes={nodeTypes}
        onInit={(instance) => {
          reactFlowInstanceRef.current = instance;
        }}
        onMoveStart={() => setUserHasMoved(true)}
        selectionOnDrag={!isCompact && interactionMode === "select"}
        onSelectionChange={handleSelectionChange}
        panOnDrag={interactionMode === "pan"}
        onNodeClick={(step) => setSelectedStep(step)}
        fitViewOptions={FIT_VIEW_OPTIONS}
        snapGrid={SNAP_GRID}
      />
      {!isCompact && (
        <CombineStepModal
          pendingCombine={pendingCombine}
          operators={COMBINE_OPERATORS}
          onChoose={(operator) => void handleCombineCreate(operator as CombineOperator)}
          onCancel={handleCombineCancel}
        />
      )}
      {!isCompact && selectedStep && (
        <StepEditor
          step={selectedStep}
          siteId={siteId}
          recordType={strategy?.recordType || null}
          strategyId={strategy?.id || null}
          onClose={() => setSelectedStep(null)}
          onUpdate={(updates) => {
            updateStep(selectedStep.id, updates);
          }}
        />
      )}
    </div>
  );
}
