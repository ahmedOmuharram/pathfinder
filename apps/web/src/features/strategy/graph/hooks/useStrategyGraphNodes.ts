"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  startTransition,
} from "react";
import { type Edge, type Node, useNodesState, useEdgesState } from "reactflow";
import type { StrategyStep, StrategyWithMeta } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/useStrategyStore";
import { useStrategyListStore } from "@/state/useStrategyListStore";
import { validateStepsForSave } from "@/features/strategy/validation/save";
import { useWarningGroupNodes } from "@/features/strategy/graph/hooks/useWarningGroupNodes";
import { useMarkUnsavedNodes } from "@/features/strategy/graph/hooks/useMarkUnsavedNodes";
import { useSaveValidation } from "@/features/strategy/validation/useSaveValidation";
import { useSessionStore } from "@/state/useSessionStore";
import { getCombineMismatchGroups, inferStepKind } from "@/lib/strategyGraph";

const DEFAULT_NODE_WIDTH = 224;
const DEFAULT_NODE_HEIGHT = 112;

interface UseStrategyGraphNodesOptions {
  strategy: StrategyWithMeta | null;
  siteId: string;
  variant: "full" | "compact";
}

/**
 * Manages node/edge state arrays, dirty-step tracking, combine-mismatch
 * groups, warning overlay nodes, and step validation.
 */
export function useStrategyGraphNodes(options: UseStrategyGraphNodesOptions) {
  const { strategy, siteId, variant } = options;

  const chatIsStreaming = useSessionStore((state) => state.chatIsStreaming);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [lastSavedStepsVersion, setLastSavedStepsVersion] = useState(0);
  const [lastSavedSteps, setLastSavedSteps] = useState<Map<string, string>>(new Map());
  const [selectedStep, setSelectedStep] = useState<StrategyStep | null>(null);
  const nodePositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());

  const draftStrategy = useStrategyStore((state) => state.strategy);
  const setStepValidationErrors = useStrategyStore(
    (state) => state.setStepValidationErrors,
  );
  const buildPlan = useStrategyStore((state) => state.buildPlan);
  const setGraphValidationStatus = useStrategyListStore(
    (state) => state.setGraphValidationStatus,
  );

  const editableSteps = useMemo(
    () => draftStrategy?.steps || strategy?.steps || [],
    [draftStrategy?.steps, strategy?.steps],
  );

  const buildStepSignature = useCallback((step: StrategyStep) => {
    const kind = inferStepKind(step);
    return JSON.stringify({
      kind,
      displayName: step.displayName,
      searchName: step.searchName,
      operator: step.operator,
      parameters: step.parameters ?? {},
      primaryInputStepId: step.primaryInputStepId,
      secondaryInputStepId: step.secondaryInputStepId,
      recordType: step.recordType,
    });
  }, []);

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
    [warningGroupNodes, nodes],
  );

  // Model-driven graph updates arrive during chat streaming. Those updates are
  // persisted by the API when emitted, so we should not show them as "unsaved".
  useEffect(() => {
    if (variant !== "full") return;
    if (!chatIsStreaming) return;
    if (selectedStep) return;
    if (!strategy?.steps || strategy.steps.length === 0) return;
    startTransition(() => {
      setLastSavedSteps(
        new Map(strategy.steps.map((step) => [step.id, buildStepSignature(step)])),
      );
      setLastSavedStepsVersion((v) => v + 1);
    });
  }, [
    variant,
    chatIsStreaming,
    selectedStep,
    strategy?.steps,
    buildStepSignature,
    setLastSavedSteps,
    setLastSavedStepsVersion,
  ]);

  // Dirty-step tracking
  const isDraftView = !!draftStrategy && strategy?.id === draftStrategy.id;
  const planResult = buildPlan();
  const planHash = planResult ? JSON.stringify(planResult.plan) : null;
  const graphIdForValidation = draftStrategy?.id || strategy?.id || null;
  const graphHasValidationIssues = useStrategyListStore((state) =>
    graphIdForValidation ? !!state.graphValidationStatus[graphIdForValidation] : false,
  );

  const dirtyStepIds = useMemo(() => {
    void lastSavedStepsVersion;
    const dirty = new Set<string>();
    const steps = strategy?.steps || [];
    if (steps.length === 0) return dirty;
    for (const step of steps) {
      const signature = buildStepSignature(step);
      if (!lastSavedSteps.has(step.id) || lastSavedSteps.get(step.id) !== signature) {
        dirty.add(step.id);
      }
    }
    return dirty;
  }, [strategy?.steps, lastSavedStepsVersion, lastSavedSteps, buildStepSignature]);

  const dirtyStepIdsKey = useMemo(
    () => Array.from(dirtyStepIds).sort().join("|"),
    [dirtyStepIds],
  );
  const isUnsaved = dirtyStepIds.size > 0;

  // Sync node positions ref
  useEffect(() => {
    nodePositionsRef.current = new Map(
      nodes.map((n: Node) => [n.id, { x: n.position.x, y: n.position.y }]),
    );
  }, [nodes]);

  useMarkUnsavedNodes({ dirtyStepIds, dirtyKey: dirtyStepIdsKey, setNodes });

  // Validate search steps
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

  useSaveValidation({
    steps: draftStrategy?.steps || [],
    buildStepSignature,
    validate: validateSearchSteps,
    strategy,
  });

  return {
    // Raw node/edge state
    nodes,
    setNodes,
    onNodesChange,
    edges,
    setEdges,
    onEdgesChange,
    nodePositionsRef,

    // Render nodes (includes warning overlays)
    renderNodes,

    // Step selection
    selectedStep,
    setSelectedStep,
    editableSteps,

    // Dirty tracking
    isDraftView,
    planResult,
    planHash,
    graphHasValidationIssues,
    dirtyStepIds,
    isUnsaved,
    lastSavedSteps,
    setLastSavedSteps,
    lastSavedStepsVersion,
    setLastSavedStepsVersion,

    // Validation
    combineMismatchGroups,
    validateSearchSteps,
    buildStepSignature,
  } as const;
}
