import type { Step } from "@pathfinder/shared";

type NodeDeletionResult = {
  removeIds: string[];
  patches: Array<{ stepId: string; patch: Partial<Step> }>;
};

/**
 * Implements the StrategyGraph node deletion semantics:
 * - delete only the explicitly deleted nodes (no cascade)
 * - detach any remaining step inputs that referenced deleted steps
 */
export function computeNodeDeletionResult(args: {
  steps: Step[];
  deletedNodeIds: string[];
}): NodeDeletionResult {
  const { steps, deletedNodeIds } = args;
  if (steps.length === 0 || deletedNodeIds.length === 0) {
    return { removeIds: [], patches: [] };
  }

  const stepsMap = new Map(steps.map((s) => [s.id, s]));
  const toRemove = new Set<string>(deletedNodeIds.filter((id) => stepsMap.has(id)));
  if (toRemove.size === 0) return { removeIds: [], patches: [] };

  const patches: NodeDeletionResult["patches"] = [];
  for (const step of steps) {
    if (toRemove.has(step.id)) continue;
    const patch: Partial<Step> = {};
    let inputDetached = false;
    if (
      step.primaryInputStepId != null &&
      step.primaryInputStepId !== "" &&
      toRemove.has(step.primaryInputStepId)
    ) {
      patch.primaryInputStepId = null;
      inputDetached = true;
    }
    if (
      step.secondaryInputStepId != null &&
      step.secondaryInputStepId !== "" &&
      toRemove.has(step.secondaryInputStepId)
    ) {
      patch.secondaryInputStepId = null;
      inputDetached = true;
    }
    if (inputDetached && step.operator != null && step.operator !== "") {
      patch.operator = null;
      patch.colocationParams = null;
    }
    if (Object.keys(patch).length > 0) {
      patches.push({ stepId: step.id, patch });
    }
  }

  return { removeIds: Array.from(toRemove), patches };
}
