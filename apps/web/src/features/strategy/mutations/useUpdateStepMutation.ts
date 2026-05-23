"use client";

import type { Step } from "@pathfinder/shared";
import { combineOpEnum, type CombineOp } from "@pathfinder/shared/generated/types/CombineOp";
import type { GraphOperation } from "@/features/strategy/operations";
import { useApplyOperation } from "./useApplyOperation";

export interface UpdateStepVars {
  stepId: string;
  patch: Partial<Step>;
}

export const STEP_PATCH_MUTATION_KEY = ["strategy", "operation"] as const;

function isCombineOp(value: string): value is CombineOp {
  return Object.values(combineOpEnum).includes(value as CombineOp);
}

function patchToOps(stepId: string, patch: Partial<Step>): GraphOperation[] {
  const ops: GraphOperation[] = [];
  if (patch.parameters !== undefined && patch.parameters !== null) {
    ops.push({
      kind: "updateStepParams",
      stepId,
      parameters: patch.parameters,
    });
  }
  if (patch.operator !== undefined) {
    if (patch.operator !== null && isCombineOp(patch.operator)) {
      ops.push({
        kind: "updateCombineOperator",
        stepId,
        operator: patch.operator,
        ...(patch.colocationParams !== undefined && {
          colocationParams: patch.colocationParams,
        }),
      });
    }
  }
  if (patch.displayName !== undefined && patch.displayName !== null) {
    ops.push({ kind: "updateStepMeta", stepId, displayName: patch.displayName });
  }
  return ops;
}

export function useUpdateStepMutation(conversationId: string) {
  const apply = useApplyOperation(conversationId);
  return {
    ...apply,
    mutate: (vars: UpdateStepVars) => {
      const ops = patchToOps(vars.stepId, vars.patch);
      for (const op of ops) {
        apply.mutate({ op });
      }
    },
    mutateAsync: async (vars: UpdateStepVars) => {
      const ops = patchToOps(vars.stepId, vars.patch);
      let last;
      for (const op of ops) {
        last = await apply.mutateAsync({ op });
      }
      return last;
    },
  };
}
