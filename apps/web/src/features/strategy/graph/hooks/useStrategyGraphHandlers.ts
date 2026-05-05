"use client";

import { useState } from "react";
import type { Edge, Node } from "@xyflow/react";
import type { Step, Strategy } from "@pathfinder/shared";
import { computeOrthologInsert } from "@/features/strategy/graph/utils/orthologInsert";
import { useDeleteOperation } from "@/features/strategy/graph/hooks/useDeleteOperation";
import {
  useAddStepMutation,
  useUpdateStepMutation,
} from "@/features/strategy/mutations";

interface UseStrategyGraphHandlersOptions {
  strategy: Strategy | null;
  isCompact: boolean;
  editableSteps: Step[];
  selectedStep: Step | null;
  setSelectedStep: (step: Step | null) => void;
  selectedNodeIds: string[];
  startCombine: (sourceId: string, targetId: string) => void;
}

/**
 * Click, combine, delete, edge-context, and ortholog-transform handlers for
 * the strategy graph. All writes go through mutations.
 */
export function useStrategyGraphHandlers(options: UseStrategyGraphHandlersOptions) {
  const {
    strategy,
    isCompact,
    editableSteps,
    selectedStep,
    setSelectedStep,
    selectedNodeIds,
    startCombine,
  } = options;

  const conversationId = strategy?.id ?? "";
  const updateStep = useUpdateStepMutation(conversationId);
  const deleteOp = useDeleteOperation(conversationId);
  const addStep = useAddStepMutation(conversationId);

  const [edgeMenu, setEdgeMenu] = useState<{
    edge: Edge;
    x: number;
    y: number;
  } | null>(null);
  const [orthologModalOpen, setOrthologModalOpen] = useState(false);

  const handleNodesDelete = (deletedNodes: Node[]) => {
    if (isCompact || deletedNodes.length === 0) return;
    const ids = deletedNodes.map((n) => n.id);
    if (ids.length === 1) {
      deleteOp.requestDelete(ids[0]!);
    } else {
      deleteOp.requestDeleteMany(ids);
    }
    if (selectedStep && ids.includes(selectedStep.id)) {
      setSelectedStep(null);
    }
  };

  const handleStartCombineFromSelection = () => {
    if (isCompact) return;
    if (selectedNodeIds.length !== 2) return;
    const first = selectedNodeIds[0];
    const second = selectedNodeIds[1];
    if (first != null && second != null) {
      startCombine(first, second);
    }
  };

  const handleStartOrthologTransformFromSelection = () => {
    if (isCompact) return;
    if (selectedNodeIds.length !== 1) return;
    setOrthologModalOpen(true);
  };

  const handleOpenDetails = (stepId: string) => {
    const step = editableSteps.find((item) => item.id === stepId);
    if (step) {
      setSelectedStep(step);
    }
  };

  const handleOrthologChoose = (
    search: Parameters<typeof computeOrthologInsert>[0]["search"],
    options: Parameters<typeof computeOrthologInsert>[0]["options"],
  ) => {
    const selectedId = selectedNodeIds[0];
    if (selectedId == null || selectedId === "") return;
    const stepsList = strategy?.steps ?? [];
    const { newStep, downstreamPatch } = computeOrthologInsert({
      selectedId,
      steps: stepsList,
      strategyRecordType: strategy?.recordType ?? null,
      search,
      options,
      generateId: () => `step_${Math.random().toString(16).slice(2, 10)}`,
    });

    addStep.mutate({ step: newStep });
    if (downstreamPatch) {
      updateStep.mutate({
        stepId: downstreamPatch.stepId,
        patch: downstreamPatch.patch,
      });
    }

    setOrthologModalOpen(false);
    setSelectedStep(newStep);
  };

  return {
    edgeMenu,
    setEdgeMenu,
    orthologModalOpen,
    setOrthologModalOpen,
    handleNodesDelete,
    handleStartCombineFromSelection,
    handleStartOrthologTransformFromSelection,
    handleOpenDetails,
    handleOrthologChoose,
    /** Single-step patch — wraps useUpdateStepMutation. */
    updateStep: (stepId: string, patch: Partial<Step>) =>
      updateStep.mutate({ stepId, patch }),
    requestDelete: deleteOp.requestDelete,
    requestDeleteMany: deleteOp.requestDeleteMany,
    deleteDialogProps: deleteOp.dialogProps,
  } as const;
}
