"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { type Node, useNodesState, useEdgesState } from "reactflow";
import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { validateStepsForSave } from "@/features/strategy/validation/save";
import { useSaveValidation } from "@/features/strategy/validation/useSaveValidation";
import {
  getCombineMismatchGroups,
  inferStepKind,
  serializeStrategyPlan,
  type CombineMismatchGroup,
} from "@/lib/strategyGraph";

const DEFAULT_NODE_WIDTH = 224;
const DEFAULT_NODE_HEIGHT = 112;
const WARNING_PADDING = 16;

function computeWarningGroupNodes(
  nodes: Node[],
  groups: CombineMismatchGroup[],
): Node[] {
  if (groups.length === 0) return [];
  return groups.flatMap((group) => {
    const targetNodes = nodes.filter((node) => group.ids.has(node.id));
    if (targetNodes.length < 2) return [];
    const minX = Math.min(...targetNodes.map((n) => n.position.x));
    const minY = Math.min(...targetNodes.map((n) => n.position.y));
    const maxX = Math.max(
      ...targetNodes.map((n) => n.position.x + (n.width ?? DEFAULT_NODE_WIDTH)),
    );
    const maxY = Math.max(
      ...targetNodes.map((n) => n.position.y + (n.height ?? DEFAULT_NODE_HEIGHT)),
    );
    const groupWidth = maxX - minX + WARNING_PADDING * 2;
    const groupHeight = maxY - minY + WARNING_PADDING * 2;
    const groupLeft = minX - WARNING_PADDING;
    const groupTop = minY - WARNING_PADDING;
    return [
      {
        id: `warning-group-${group.id}`,
        type: "warningGroup",
        position: { x: groupLeft, y: groupTop },
        data: { message: group.message },
        className: "warning-group-node warning-dash",
        selectable: false,
        draggable: false,
        connectable: false,
        deletable: false,
        focusable: false,
        width: groupWidth,
        height: groupHeight,
        style: {
          width: groupWidth,
          height: groupHeight,
          zIndex: 50,
          pointerEvents: "none",
          background: "transparent",
          overflow: "visible",
          borderRadius: 14,
          boxSizing: "border-box",
        },
      } as Node,
      {
        id: `warning-icon-${group.id}`,
        type: "warningIcon",
        position: { x: groupLeft - 8, y: groupTop - 8 },
        data: { message: group.message },
        selectable: false,
        draggable: false,
        connectable: false,
        deletable: false,
        focusable: false,
        width: 24,
        height: 24,
        style: {
          width: 24,
          height: 24,
          zIndex: 60,
          pointerEvents: "auto",
          background: "transparent",
        },
      } as Node,
    ];
  });
}

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

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedStep, setSelectedStep] = useState<Step | null>(null);
  const nodePositionsRef = useRef<Map<string, { x: number; y: number }>>(new Map());

  const draftStrategy = useStrategyStore((state) => state.strategy);
  const setStepValidationErrors = useStrategyStore(
    (state) => state.setStepValidationErrors,
  );
  const stepsById = useStrategyStore((state) => state.stepsById);
  const setGraphValidationStatus = useStrategyStore(
    (state) => state.setGraphValidationStatus,
  );

  const editableSteps = useMemo(
    () => draftStrategy?.steps ?? strategy?.steps ?? [],
    [draftStrategy?.steps, strategy?.steps],
  );

  const buildStepSignature = useCallback((step: Step) => {
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
    const steps = draftStrategy?.steps ?? strategy?.steps ?? [];
    return getCombineMismatchGroups(steps);
  }, [draftStrategy?.steps, strategy?.steps]);

  const warningGroupNodes = useMemo(
    () => computeWarningGroupNodes(nodes, combineMismatchGroups),
    [nodes, combineMismatchGroups],
  );

  const isDraftView = draftStrategy != null && strategy?.id === draftStrategy.id;
  const planResult = useMemo(
    () => serializeStrategyPlan(stepsById, draftStrategy ?? strategy),
    [stepsById, draftStrategy, strategy],
  );
  const planHash = useMemo(
    () => (planResult ? JSON.stringify(planResult.plan) : null),
    [planResult],
  );
  const graphIdForValidation = draftStrategy?.id ?? strategy?.id ?? null;
  const graphHasValidationIssues = useStrategyStore((state) =>
    graphIdForValidation != null && graphIdForValidation !== ""
      ? state.graphValidationStatus[graphIdForValidation] === true
      : false,
  );

  // Render nodes (warning overlays only -- no dirty dots)
  const renderNodes = useMemo(() => {
    return warningGroupNodes.length > 0
      ? [...warningGroupNodes, ...nodes]
      : nodes;
  }, [warningGroupNodes, nodes]);

  // Sync node positions ref
  useEffect(() => {
    nodePositionsRef.current = new Map(
      nodes.map((n: Node) => [n.id, { x: n.position.x, y: n.position.y }]),
    );
  }, [nodes]);

  // Validate search steps
  const validateSearchSteps = useCallback(async () => {
    const steps = draftStrategy?.steps ?? [];
    if (steps.length === 0) return true;
    const { errorsByStepId, hasErrors: hasFieldErrors } = await validateStepsForSave({
      siteId,
      steps,
      strategy,
    });
    setStepValidationErrors(errorsByStepId);
    const hasErrors = hasFieldErrors || combineMismatchGroups.length > 0;
    const graphId = draftStrategy?.id ?? strategy?.id;
    if (graphId != null && graphId !== "") {
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
    nodePositionsRef,

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
