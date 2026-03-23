import type { Strategy } from "@pathfinder/shared";
import type { NodeSelection, NodeSelectionNode } from "@/lib/types/nodeSelection";
import { inferStepKind } from "@/lib/strategyGraph";

export function buildNodeSelectionPayload(
  strategy: Strategy | null,
  nodeIds: string[],
): NodeSelection {
  const snapshotId = strategy?.id;
  const selectedSet = new Set(nodeIds);
  const contextSet = new Set(nodeIds);
  const steps = strategy?.steps ?? [];

  // Add direct inputs of selected nodes to context.
  for (const step of steps) {
    if (!selectedSet.has(step.id)) continue;
    if (step.primaryInputStepId != null && step.primaryInputStepId !== "")
      contextSet.add(step.primaryInputStepId);
    if (step.secondaryInputStepId != null && step.secondaryInputStepId !== "")
      contextSet.add(step.secondaryInputStepId);
  }

  // Add parents of selected inputs (one-hop).
  for (const step of steps) {
    if (
      (step.primaryInputStepId != null &&
        step.primaryInputStepId !== "" &&
        selectedSet.has(step.primaryInputStepId)) ||
      (step.secondaryInputStepId != null &&
        step.secondaryInputStepId !== "" &&
        selectedSet.has(step.secondaryInputStepId))
    ) {
      contextSet.add(step.id);
    }
  }

  const nodes: NodeSelectionNode[] = steps
    .filter((step) => contextSet.has(step.id))
    .map((step) => {
      const node: NodeSelectionNode = {
        id: step.id,
        kind: inferStepKind(step),
        displayName: step.displayName ?? "",
        selected: selectedSet.has(step.id),
      };
      if (step.searchName) node.searchName = step.searchName;
      if (step.operator != null) node.operator = step.operator;
      if (step.parameters != null) node.parameters = step.parameters;
      if (step.recordType != null) node.recordType = step.recordType;
      if (step.estimatedSize != null) node.estimatedSize = step.estimatedSize;
      if (step.wdkStepId != null) node.wdkStepId = step.wdkStepId;
      return node;
    });

  const edges: Array<{ sourceId: string; targetId: string; kind: string }> = [];
  for (const step of steps) {
    if (!contextSet.has(step.id)) continue;
    if (
      step.primaryInputStepId != null &&
      step.primaryInputStepId !== "" &&
      contextSet.has(step.primaryInputStepId)
    ) {
      edges.push({
        sourceId: step.primaryInputStepId,
        targetId: step.id,
        kind: "primary",
      });
    }
    if (
      step.secondaryInputStepId != null &&
      step.secondaryInputStepId !== "" &&
      contextSet.has(step.secondaryInputStepId)
    ) {
      edges.push({
        sourceId: step.secondaryInputStepId,
        targetId: step.id,
        kind: "secondary",
      });
    }
  }

  const result: NodeSelection = {
    nodeIds,
    selectedNodeIds: nodeIds,
    contextNodeIds: Array.from(contextSet),
    nodes,
    edges,
  };
  if (snapshotId != null) {
    result.graphId = snapshotId;
  }
  return result;
}
