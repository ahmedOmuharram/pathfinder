import { useState } from "react";
import type { Connection, Edge } from "@xyflow/react";
import { type CombineOperator } from "@pathfinder/shared";
import type { Step } from "@pathfinder/shared";
import {
  buildGraphIndices,
  edgeToInputPatch,
  getConnectionEffect,
  inferCombineRecordTypeOrMismatch,
  isValidGraphConnection,
} from "@/features/strategy/graph/utils/graphConnectionsLogic";

interface PendingCombine {
  sourceId: string;
  targetId: string;
}

interface UseGraphConnectionsArgs {
  steps: Step[];
  addStep: (step: Step) => void;
  updateStep: (stepId: string, updates: Partial<Step>) => void;
  failCombineMismatch: () => void;
  triggerSync: () => void;
}

const generateStepId = () => `step_${Math.random().toString(16).slice(2, 10)}`;

export function useGraphConnections({
  steps,
  addStep,
  updateStep,
  failCombineMismatch,
  triggerSync,
}: UseGraphConnectionsArgs) {
  const [pendingCombine, setPendingCombine] = useState<PendingCombine | null>(null);
  const indices = buildGraphIndices(steps);

  const isValidConnection = (connection: Edge | Connection) => {
    return isValidGraphConnection(connection as Connection, indices);
  };

  const handleConnect = (connection: Connection) => {
    const effect = getConnectionEffect(connection, indices);
    if (effect.type === "patch") {
      updateStep(effect.targetId, effect.patch);
      triggerSync();
    } else if (effect.type === "pendingCombine") {
      setPendingCombine({ sourceId: effect.sourceId, targetId: effect.targetId });
    }
  };

  const handleDeleteEdge = (edge: Edge) => {
    const patch = edgeToInputPatch(edge);
    if (!patch) return;
    updateStep(edge.target, patch);
    triggerSync();
  };

  const handleCombineCreate = async (operator: CombineOperator) => {
    if (!pendingCombine) return;
    const { recordType, mismatch } = inferCombineRecordTypeOrMismatch({
      sourceId: pendingCombine.sourceId,
      targetId: pendingCombine.targetId,
      indices,
    });
    if (mismatch) {
      failCombineMismatch();
      setPendingCombine(null);
      return;
    }
    const nextStep: Step = {
      id: generateStepId(),
      kind: "combine",
      displayName: `${operator} combine`,
      operator,
      recordType: recordType ?? null,
      primaryInputStepId: pendingCombine.sourceId,
      secondaryInputStepId: pendingCombine.targetId,
      isBuilt: false,
      isFiltered: false,
    };
    addStep(nextStep);
    setPendingCombine(null);
    triggerSync();
  };

  const handleCombineCancel = () => {
    setPendingCombine(null);
  };

  const startCombine = (sourceId: string, targetId: string) => {
    if (!sourceId || !targetId) return;
    if (sourceId === targetId) return;
    // Only meaningful when the graph has multiple roots and both selections are roots.
    if (indices.rootIds.length === 1) return;
    if (!indices.rootSet.has(sourceId) || !indices.rootSet.has(targetId)) return;
    setPendingCombine({ sourceId, targetId });
  };

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
