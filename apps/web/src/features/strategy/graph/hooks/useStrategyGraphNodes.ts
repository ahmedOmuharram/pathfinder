"use client";

import { useState } from "react";
import { type Node, type Edge, useNodesState, useEdgesState } from "@xyflow/react";
import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { useStepsById } from "@/state/strategy/selectors";
import { validateStepsForSave } from "@/features/strategy/validation/save";
import { useSaveValidation } from "@/features/strategy/validation/useSaveValidation";
import {
  getCombineMismatchGroups,
  inferStepKind,
  serializeStrategyAst,
} from "@/lib/strategyGraph";

interface UseStrategyGraphNodesOptions {
  strategy: Strategy | null;
  siteId: string;
  variant: "full" | "compact";
}

/**
 * Manages node/edge state arrays, combine-mismatch
 * groups, warning overlay nodes, and step validation.
 */
export function useStrategyGraphNodes(options: UseStrategyGraphNodesOptions) {
  const { strategy, siteId } = options;

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedStep, setSelectedStep] = useState<Step | null>(null);
  const nodePositions = new Map(nodes.map((n: Node) => [n.id, { x: n.position.x, y: n.position.y }]));

  const draftStrategy = useStrategyStore((state) => state.strategy);
  const applyStepValidationErrors = useStrategyStore(
    (state) => state.applyStepValidationErrors,
  );
  const stepsById = useStepsById();
  const setGraphValidationStatus = useStrategyStore(
    (state) => state.setGraphValidationStatus,
  );

  const editableSteps = draftStrategy?.steps ?? strategy?.steps ?? [];

  const buildStepSignature = (step: Step) => {
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
  };

  const combineMismatchGroups = getCombineMismatchGroups(draftStrategy?.steps ?? strategy?.steps ?? []);

  const isDraftView = draftStrategy != null && strategy?.id === draftStrategy.id;
  const planResult = serializeStrategyAst(stepsById, draftStrategy ?? strategy);
  const planHash = planResult ? JSON.stringify(planResult.plan) : null;
  const graphIdForValidation = draftStrategy?.id ?? strategy?.id ?? null;
  const graphHasValidationIssues = useStrategyStore((state) =>
    graphIdForValidation != null && graphIdForValidation !== ""
      ? state.graphValidationStatus[graphIdForValidation] === true
      : false,
  );

  // Validation Alert renders as canvas chrome (see ValidationAlert) instead of
  // injecting overlay nodes into the graph itself.
  const renderNodes = nodes;


  // Validate search steps
  const validateSearchSteps = async () => {
    const steps = draftStrategy?.steps ?? [];
    if (steps.length === 0) return true;
    const { errorsByStepId, hasErrors: hasFieldErrors } = await validateStepsForSave({
      siteId,
      steps,
      strategy,
    });
    applyStepValidationErrors(errorsByStepId);
    const hasErrors = hasFieldErrors || combineMismatchGroups.length > 0;
    const graphId = draftStrategy?.id ?? strategy?.id;
    if (graphId != null && graphId !== "") {
      setGraphValidationStatus(graphId, hasErrors);
    }
    return !hasErrors;
  };

  useSaveValidation({
    steps: draftStrategy?.steps ?? [],
    buildStepSignature,
    validate: validateSearchSteps,
  });

  return {
    // Raw node/edge state
    nodes,
    setNodes,
    onNodesChange,
    edges,
    setEdges,
    onEdgesChange,
    nodePositions,

    // Render nodes (includes warning overlays)
    renderNodes,

    // Step selection
    selectedStep,
    setSelectedStep,
    editableSteps,

    // Graph metadata
    isDraftView,
    planResult,
    planHash,
    graphHasValidationIssues,

    // Validation
    combineMismatchGroups,
    validateSearchSteps,
    buildStepSignature,
  } as const;
}
