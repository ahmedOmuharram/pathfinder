import { useCallback, useMemo, useState } from "react";
import type { Connection, Edge } from "reactflow";
import { CombineOperator } from "@pathfinder/shared";
import type { StrategyStep } from "@/types/strategy";
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
  steps: StrategyStep[];
  addStep: (step: StrategyStep) => void;
  updateStep: (stepId: string, updates: Partial<StrategyStep>) => void;
  failCombineMismatch: () => void;
}

const generateStepId = () => `step_${Math.random().toString(16).slice(2, 10)}`;

export function useGraphConnections({
  steps,
  addStep,
  updateStep,
  failCombineMismatch,
}: UseGraphConnectionsArgs) {
  const [pendingCombine, setPendingCombine] = useState<PendingCombine | null>(null);
  const indices = useMemo(() => buildGraphIndices(steps), [steps]);

  const isValidConnection = useCallback(
    (connection: Connection) => {
      return isValidGraphConnection(connection, indices);
    },
    [indices],
  );

  const handleConnect = useCallback(
    (connection: Connection) => {
      const effect = getConnectionEffect(connection, indices);
      if (effect.type === "patch") {
        updateStep(effect.targetId, effect.patch);
      } else if (effect.type === "pendingCombine") {
        setPendingCombine({ sourceId: effect.sourceId, targetId: effect.targetId });
      }
    },
    [indices, updateStep],
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
      const nextStep: StrategyStep = {
        id: generateStepId(),
        kind: "combine",
        displayName: `${operator} combine`,
        operator,
        recordType: recordType ?? undefined,
        primaryInputStepId: pendingCombine.sourceId,
        secondaryInputStepId: pendingCombine.targetId,
      };
      addStep(nextStep);
      setPendingCombine(null);
    },
    [pendingCombine, indices, addStep, failCombineMismatch],
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
