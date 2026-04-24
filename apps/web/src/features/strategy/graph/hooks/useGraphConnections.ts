"use client";

import { toast } from "sonner";
import type { Connection, Edge } from "@xyflow/react";
import type { Step } from "@pathfinder/shared";
import {
  buildGraphIndices,
  edgeToInputPatch,
  getConnectionEffect,
  inferCombineRecordTypeOrMismatch,
  isValidGraphConnection,
} from "@/features/strategy/graph/utils/graphConnectionsLogic";
import {
  useAddStepMutation,
  useUpdateStepMutation,
} from "@/features/strategy/mutations";

interface UseGraphConnectionsArgs {
  steps: Step[];
  conversationId: string;
}

const COMBINE_MISMATCH_ERROR = "Cannot combine steps with different record types.";
const generateStepId = () => `step_${Math.random().toString(16).slice(2, 10)}`;

/**
 * Connection handlers for the strategy graph.
 *
 * The pre-overhaul "pick combine operator first" modal flow is gone; dragging
 * an edge between two roots now creates a combine step with the default
 * `INTERSECT` operator. The user picks a different operator from the editor
 * Sheet (or the edge ContextMenu) afterwards.
 */
export function useGraphConnections({ steps, conversationId }: UseGraphConnectionsArgs) {
  const addStep = useAddStepMutation(conversationId);
  const updateStep = useUpdateStepMutation(conversationId);
  const indices = buildGraphIndices(steps);

  const isValidConnection = (connection: Edge | Connection) =>
    isValidGraphConnection(connection as Connection, indices);

  const handleConnect = (connection: Connection) => {
    const effect = getConnectionEffect(connection, indices);
    if (effect.type === "patch") {
      updateStep.mutate({ stepId: effect.targetId, patch: effect.patch });
      return;
    }
    if (effect.type === "pendingCombine") {
      const { recordType, mismatch } = inferCombineRecordTypeOrMismatch({
        sourceId: effect.sourceId,
        targetId: effect.targetId,
        indices,
      });
      if (mismatch) {
        toast.error(COMBINE_MISMATCH_ERROR);
        return;
      }
      const newStep: Step = {
        id: generateStepId(),
        kind: "combine",
        displayName: "INTERSECT combine",
        operator: "INTERSECT",
        recordType: recordType ?? null,
        primaryInputStepId: effect.sourceId,
        secondaryInputStepId: effect.targetId,
        isBuilt: false,
        isFiltered: false,
      };
      addStep.mutate({ step: newStep });
    }
  };

  const handleDeleteEdge = (edge: Edge) => {
    const patch = edgeToInputPatch(edge);
    if (!patch) return;
    updateStep.mutate({ stepId: edge.target, patch });
  };

  const startCombine = (sourceId: string, targetId: string) => {
    if (!sourceId || !targetId || sourceId === targetId) return;
    if (indices.rootIds.length === 1) return;
    if (!indices.rootSet.has(sourceId) || !indices.rootSet.has(targetId)) return;
    const { recordType, mismatch } = inferCombineRecordTypeOrMismatch({
      sourceId,
      targetId,
      indices,
    });
    if (mismatch) {
      toast.error(COMBINE_MISMATCH_ERROR);
      return;
    }
    const newStep: Step = {
      id: generateStepId(),
      kind: "combine",
      displayName: "INTERSECT combine",
      operator: "INTERSECT",
      recordType: recordType ?? null,
      primaryInputStepId: sourceId,
      secondaryInputStepId: targetId,
      isBuilt: false,
      isFiltered: false,
    };
    addStep.mutate({ step: newStep });
  };

  return {
    isValidConnection,
    handleConnect,
    handleDeleteEdge,
    startCombine,
  };
}
