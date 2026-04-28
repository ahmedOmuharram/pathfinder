import type { Strategy } from "@pathfinder/shared";
import { findParent, walkSubtreeIds } from "./utils";
import { patchSteps } from "./_patch";
import type { ApplyResult, GraphOperation } from "./types";

type UpdateParamsOp = Extract<GraphOperation, { kind: "updateStepParams" }>;
type UpdateOpOp = Extract<GraphOperation, { kind: "updateCombineOperator" }>;
type UpdateMetaOp = Extract<GraphOperation, { kind: "updateStepMeta" }>;
type ReplaceOp = Extract<GraphOperation, { kind: "replaceSubtree" }>;
type DeleteEdgeOp = Extract<GraphOperation, { kind: "deleteEdge" }>;

export function applyUpdateStepParams(
  strategy: Strategy,
  op: UpdateParamsOp,
): ApplyResult {
  if (!strategy.steps.some((s) => s.id === op.stepId))
    return { kind: "rejected", reason: `Step ${op.stepId} not found` };
  return {
    kind: "applied",
    next: {
      ...strategy,
      steps: patchSteps(strategy.steps, op.stepId, { parameters: op.parameters }),
    },
    description: `Updated parameters of ${op.stepId}`,
  };
}

export function applyUpdateCombineOperator(
  strategy: Strategy,
  op: UpdateOpOp,
): ApplyResult {
  if (!strategy.steps.some((s) => s.id === op.stepId))
    return { kind: "rejected", reason: `Step ${op.stepId} not found` };
  return {
    kind: "applied",
    next: {
      ...strategy,
      steps: patchSteps(strategy.steps, op.stepId, {
        operator: op.operator,
        colocationParams: op.colocationParams ?? null,
      }),
    },
    description: `Set operator of ${op.stepId} to ${op.operator}`,
  };
}

export function applyUpdateStepMeta(
  strategy: Strategy,
  op: UpdateMetaOp,
): ApplyResult {
  if (!strategy.steps.some((s) => s.id === op.stepId))
    return { kind: "rejected", reason: `Step ${op.stepId} not found` };
  return {
    kind: "applied",
    next: {
      ...strategy,
      steps: patchSteps(strategy.steps, op.stepId, {
        displayName: op.displayName,
      }),
    },
    description: `Renamed ${op.stepId}`,
  };
}

export function applyReplaceSubtree(
  strategy: Strategy,
  op: ReplaceOp,
): ApplyResult {
  const newRoot = op.subtree[op.subtree.length - 1];
  if (newRoot === undefined)
    return {
      kind: "rejected",
      reason: "replaceSubtree requires non-empty subtree",
    };
  const oldSubtree = new Set(walkSubtreeIds(strategy.steps, op.stepId));
  const parentInfo = findParent(strategy.steps, op.stepId);
  let next = strategy.steps.filter((s) => !oldSubtree.has(s.id));
  next = [...next, ...op.subtree];
  if (parentInfo !== null) {
    const slotKey =
      parentInfo.slot === "primary"
        ? "primaryInputStepId"
        : "secondaryInputStepId";
    next = patchSteps(next, parentInfo.parent.id, { [slotKey]: newRoot.id });
  }
  return {
    kind: "applied",
    next: { ...strategy, steps: next },
    description: `Replaced subtree at ${op.stepId}`,
  };
}

export function applyDeleteEdge(
  strategy: Strategy,
  op: DeleteEdgeOp,
  recurse: (s: Strategy, op: GraphOperation) => ApplyResult,
): ApplyResult {
  if (!strategy.steps.some((s) => s.id === op.targetId))
    return { kind: "rejected", reason: `Target ${op.targetId} not found` };
  if (op.resolution === "detach") {
    const slotKey =
      op.slot === "primary" ? "primaryInputStepId" : "secondaryInputStepId";
    return {
      kind: "applied",
      next: {
        ...strategy,
        steps: patchSteps(strategy.steps, op.targetId, {
          [slotKey]: null,
          operator: null,
          colocationParams: null,
        }),
      },
      description: `Detached edge ${op.sourceId} → ${op.targetId}`,
    };
  }
  return recurse(strategy, {
    kind: "deleteStep",
    stepId: op.sourceId,
    resolution: "collapse-combine",
  });
}
