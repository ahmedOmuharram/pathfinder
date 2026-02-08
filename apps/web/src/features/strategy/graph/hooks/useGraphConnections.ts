import { useCallback, useMemo, useState } from "react";
import type { Connection, Edge } from "reactflow";
import { CombineOperator } from "@pathfinder/shared";
import type { StrategyStep } from "@/types/strategy";
import { resolveRecordType } from "@/features/strategy/domain/graph";
import { inferStepKind } from "@/core/strategyGraph";

interface PendingCombine {
  sourceId: string;
  targetId: string;
}

interface UseGraphConnectionsArgs {
  steps: StrategyStep[];
  addStep: (step: StrategyStep) => void;
  updateStep: (stepId: string, updates: Partial<StrategyStep>) => void;
  failCombineMismatch: () => void;
}

const generateStepId = () => `step_${Math.random().toString(16).slice(2, 10)}`;

function buildIndices(steps: StrategyStep[]) {
  const stepsById = new Map<string, StrategyStep>();
  const usedAsInputCount = new Map<string, number>();
  for (const step of steps) {
    stepsById.set(step.id, step);
  }
  for (const step of steps) {
    if (step.primaryInputStepId) {
      usedAsInputCount.set(
        step.primaryInputStepId,
        (usedAsInputCount.get(step.primaryInputStepId) ?? 0) + 1,
      );
    }
    if (step.secondaryInputStepId) {
      usedAsInputCount.set(
        step.secondaryInputStepId,
        (usedAsInputCount.get(step.secondaryInputStepId) ?? 0) + 1,
      );
    }
  }
  const rootIds = steps
    .map((s) => s.id)
    .filter((id) => (usedAsInputCount.get(id) ?? 0) === 0);
  return {
    stepsById,
    usedAsInputCount,
    rootIds,
    rootSet: new Set(rootIds),
  };
}

function isUpstream(
  sourceId: string,
  maybeUpstreamId: string,
  stepsById: Map<string, StrategyStep>,
) {
  // Walk upstream pointers (inputs) starting from sourceId.
  const visited = new Set<string>();
  const stack = [sourceId];
  while (stack.length) {
    const current = stack.pop()!;
    if (current === maybeUpstreamId) return true;
    if (visited.has(current)) continue;
    visited.add(current);
    const step = stepsById.get(current);
    if (!step) continue;
    if (step.primaryInputStepId) stack.push(step.primaryInputStepId);
    if (step.secondaryInputStepId) stack.push(step.secondaryInputStepId);
  }
  return false;
}

function edgeToInputPatch(edge: Edge): Partial<StrategyStep> | null {
  if (edge.targetHandle === "left") return { primaryInputStepId: undefined };
  if (edge.targetHandle === "left-secondary")
    return { secondaryInputStepId: undefined };
  if (edge.id.endsWith("-primary")) return { primaryInputStepId: undefined };
  if (edge.id.endsWith("-secondary")) return { secondaryInputStepId: undefined };
  return null;
}

export function useGraphConnections({
  steps,
  addStep,
  updateStep,
  failCombineMismatch,
}: UseGraphConnectionsArgs) {
  const [pendingCombine, setPendingCombine] = useState<PendingCombine | null>(null);
  const indices = useMemo(() => buildIndices(steps), [steps]);

  const isValidConnection = useCallback(
    (connection: Connection) => {
      const sourceId = connection.source;
      const targetId = connection.target;
      if (!sourceId || !targetId) return false;
      if (sourceId === targetId) return false;

      const sourceStep = indices.stepsById.get(sourceId);
      const targetStep = indices.stepsById.get(targetId);
      if (!sourceStep || !targetStep) return false;

      // Once a step's output is connected (used as input), it cannot be reused.
      const sourceIsRoot = indices.rootSet.has(sourceId);
      if (!sourceIsRoot) return false;

      if (connection.targetHandle === "left") {
        const kind = inferStepKind(targetStep);
        if (kind !== "transform" && kind !== "combine") return false;
        if (targetStep.primaryInputStepId) return false;
        if (isUpstream(sourceId, targetId, indices.stepsById)) return false;
        return true;
      }
      if (connection.targetHandle === "left-secondary") {
        const kind = inferStepKind(targetStep);
        if (kind !== "combine") return false;
        if (targetStep.secondaryInputStepId) return false;
        if (isUpstream(sourceId, targetId, indices.stepsById)) return false;
        return true;
      }

      // Otherwise treat as "combine two outputs" gesture.
      // Only possible/meaningful when the graph has multiple outputs (roots).
      if (indices.rootIds.length === 1) return false;
      if (!indices.rootSet.has(targetId)) return false;
      return true;
    },
    [indices],
  );

  const handleConnect = useCallback(
    (connection: Connection) => {
      if (!isValidConnection(connection)) return;
      const sourceId = connection.source!;
      const targetId = connection.target!;

      if (connection.targetHandle === "left") {
        updateStep(targetId, { primaryInputStepId: sourceId });
        return;
      }
      if (connection.targetHandle === "left-secondary") {
        updateStep(targetId, { secondaryInputStepId: sourceId });
        return;
      }
      setPendingCombine({ sourceId, targetId });
    },
    [isValidConnection, updateStep],
  );

  const handleDeleteEdge = useCallback(
    (edge: Edge) => {
      const patch = edgeToInputPatch(edge);
      if (!patch) return;
      updateStep(edge.target, patch);
    },
    [updateStep],
  );

  const handleCombineCreate = useCallback(
    async (operator: CombineOperator) => {
      if (!pendingCombine) return;
      let inferredRecordType: string | null = null;
      if (steps.length) {
        const leftType = resolveRecordType(pendingCombine.sourceId, indices.stepsById);
        const rightType = resolveRecordType(pendingCombine.targetId, indices.stepsById);
        inferredRecordType =
          leftType && leftType !== "__mismatch__" ? leftType : rightType;
        if (
          leftType &&
          rightType &&
          leftType !== rightType &&
          leftType !== "__mismatch__" &&
          rightType !== "__mismatch__"
        ) {
          failCombineMismatch();
          setPendingCombine(null);
          return;
        }
      }
      const nextStep: StrategyStep = {
        id: generateStepId(),
        kind: "combine",
        displayName: `${operator} combine`,
        operator,
        recordType: inferredRecordType ?? undefined,
        primaryInputStepId: pendingCombine.sourceId,
        secondaryInputStepId: pendingCombine.targetId,
      };
      addStep(nextStep);
      setPendingCombine(null);
    },
    [pendingCombine, steps.length, indices.stepsById, addStep, failCombineMismatch],
  );

  const handleCombineCancel = useCallback(() => {
    setPendingCombine(null);
  }, []);

  const startCombine = useCallback(
    (sourceId: string, targetId: string) => {
      if (!sourceId || !targetId) return;
      if (sourceId === targetId) return;
      // Only meaningful when the graph has multiple roots and both selections are roots.
      if (indices.rootIds.length === 1) return;
      if (!indices.rootSet.has(sourceId) || !indices.rootSet.has(targetId)) return;
      setPendingCombine({ sourceId, targetId });
    },
    [indices.rootIds.length, indices.rootSet],
  );

  return {
    pendingCombine,
    isValidConnection,
    handleConnect,
    handleDeleteEdge,
    handleCombineCreate,
    handleCombineCancel,
    startCombine,
  };
}
