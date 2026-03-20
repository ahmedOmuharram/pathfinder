"use client";

import { useCallback, useState } from "react";
import type { Edge, Node } from "reactflow";
import type { Step, Strategy } from "@pathfinder/shared";
import { useStrategyStore } from "@/state/strategy/store";
import { computeNodeDeletionResult } from "@/features/strategy/graph/utils/nodeDeletionLogic";
import { computeOrthologInsert } from "@/features/strategy/graph/utils/orthologInsert";

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
 * Click, combine, delete, edge-context, and ortholog-transform handlers
 * for the strategy graph.
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

  const draftStrategy = useStrategyStore((state) => state.strategy);
  const updateStep = useStrategyStore((state) => state.updateStep);
  const addStep = useStrategyStore((state) => state.addStep);
  const removeStep = useStrategyStore((state) => state.removeStep);

  const [edgeMenu, setEdgeMenu] = useState<{
    edge: Edge;
    x: number;
    y: number;
  } | null>(null);
  const [orthologModalOpen, setOrthologModalOpen] = useState(false);

  const handleNodesDelete = useCallback(
    (deletedNodes: Node[]) => {
      if (isCompact || deletedNodes.length === 0) return;
      const stepsList = draftStrategy?.steps ?? [];
      if (stepsList.length === 0) return;
      const result = computeNodeDeletionResult({
        steps: stepsList,
        deletedNodeIds: deletedNodes.map((n) => n.id),
      });
      if (result.removeIds.length === 0) return;

      for (const { stepId, patch } of result.patches) {
        updateStep(stepId, patch);
      }
      for (const stepId of result.removeIds) {
        removeStep(stepId);
      }
      if (selectedStep && result.removeIds.includes(selectedStep.id)) {
        setSelectedStep(null);
      }
    },
    [
      draftStrategy?.steps,
      isCompact,
      removeStep,
      selectedStep,
      updateStep,
      setSelectedStep,
    ],
  );

  const handleStartCombineFromSelection = useCallback(() => {
    if (isCompact) return;
    if (selectedNodeIds.length !== 2) return;
    const first = selectedNodeIds[0];
    const second = selectedNodeIds[1];
    if (first != null && second != null) {
      startCombine(first, second);
    }
  }, [isCompact, selectedNodeIds, startCombine]);

  const handleStartOrthologTransformFromSelection = useCallback(() => {
    if (isCompact) return;
    if (selectedNodeIds.length !== 1) return;
    setOrthologModalOpen(true);
  }, [isCompact, selectedNodeIds.length]);

  const handleOpenDetails = useCallback(
    (stepId: string) => {
      const step = editableSteps.find((item) => item.id === stepId);
      if (step) {
        setSelectedStep(step);
      }
    },
    [editableSteps, setSelectedStep],
  );

  const handleOrthologChoose = useCallback(
    (
      search: Parameters<typeof computeOrthologInsert>[0]["search"],
      options: Parameters<typeof computeOrthologInsert>[0]["options"],
    ) => {
      const selectedId = selectedNodeIds[0];
      if (selectedId == null || selectedId === "") return;
      const stepsList = draftStrategy?.steps ?? strategy?.steps ?? [];
      const { newStep, downstreamPatch } = computeOrthologInsert({
        selectedId,
        steps: stepsList,
        strategyRecordType: strategy?.recordType ?? null,
        search,
        options,
        generateId: () => `step_${Math.random().toString(16).slice(2, 10)}`,
      });

      addStep(newStep);
      if (downstreamPatch) {
        updateStep(downstreamPatch.stepId, downstreamPatch.patch);
      }

      setOrthologModalOpen(false);
      setSelectedStep(newStep);
    },
    [
      selectedNodeIds,
      draftStrategy?.steps,
      strategy?.steps,
      strategy?.recordType,
      addStep,
      updateStep,
      setSelectedStep,
    ],
  );

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
    updateStep,
  } as const;
}
