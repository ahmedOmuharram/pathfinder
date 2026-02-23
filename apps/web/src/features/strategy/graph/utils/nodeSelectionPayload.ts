import type { StrategyWithMeta } from "@/features/strategy/types";
import type { NodeSelection } from "@/features/chat/node_selection";
import { inferStepKind } from "@/lib/strategyGraph";

export function buildNodeSelectionPayload(
  strategy: StrategyWithMeta | null,
  nodeIds: string[],
): NodeSelection {
  const snapshotId = strategy?.id;
  const selectedSet = new Set(nodeIds);
  const contextSet = new Set(nodeIds);
  const steps = strategy?.steps || [];

  // Add direct inputs of selected nodes to context.
  for (const step of steps) {
    if (!selectedSet.has(step.id)) continue;
    if (step.primaryInputStepId) contextSet.add(step.primaryInputStepId);
    if (step.secondaryInputStepId) contextSet.add(step.secondaryInputStepId);
  }

  // Add parents of selected inputs (one-hop).
  for (const step of steps) {
    if (
      (step.primaryInputStepId && selectedSet.has(step.primaryInputStepId)) ||
      (step.secondaryInputStepId && selectedSet.has(step.secondaryInputStepId))
    ) {
      contextSet.add(step.id);
    }
  }

  const nodes =
    steps
      .filter((step) => contextSet.has(step.id))
      .map((step) => ({
        id: step.id,
        kind: inferStepKind(step),
        displayName: step.displayName,
        searchName: step.searchName,
        operator: step.operator,
        parameters: step.parameters,
        recordType: step.recordType,
        resultCount: step.resultCount,
        wdkStepId: step.wdkStepId,
        selected: selectedSet.has(step.id),
      })) || [];

  const edges: Array<{ sourceId: string; targetId: string; kind: string }> = [];
  for (const step of steps) {
    if (!contextSet.has(step.id)) continue;
    if (step.primaryInputStepId && contextSet.has(step.primaryInputStepId)) {
      edges.push({
        sourceId: step.primaryInputStepId,
        targetId: step.id,
        kind: "primary",
      });
    }
    if (step.secondaryInputStepId && contextSet.has(step.secondaryInputStepId)) {
      edges.push({
        sourceId: step.secondaryInputStepId,
        targetId: step.id,
        kind: "secondary",
      });
    }
  }

  return {
    graphId: snapshotId,
    nodeIds,
    selectedNodeIds: nodeIds,
    contextNodeIds: Array.from(contextSet),
    nodes,
    edges,
  };
}
