"use client";

import { useApplyOperation } from "./useApplyOperation";

export interface DuplicateStepVars {
  stepId: string;
}

const generateStepId = (): string =>
  `step_${Math.random().toString(16).slice(2, 10)}`;

export function useDuplicateStepMutation(conversationId: string) {
  const apply = useApplyOperation(conversationId);
  return {
    ...apply,
    mutate: (vars: DuplicateStepVars) => {
      apply.mutate({
        op: {
          kind: "duplicateStep",
          sourceStepId: vars.stepId,
          duplicateStepId: generateStepId(),
          combineStepId: generateStepId(),
        },
      });
    },
    mutateAsync: async (vars: DuplicateStepVars) => {
      return apply.mutateAsync({
        op: {
          kind: "duplicateStep",
          sourceStepId: vars.stepId,
          duplicateStepId: generateStepId(),
          combineStepId: generateStepId(),
        },
      });
    },
  };
}
