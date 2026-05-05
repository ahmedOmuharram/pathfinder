"use client";

import { useApplyOperation } from "./useApplyOperation";

export interface UpdateStrategyMetaVars {
  name?: string;
  description?: string | null;
}

export function useUpdateStrategyMetaMutation(conversationId: string) {
  const apply = useApplyOperation(conversationId);
  return {
    ...apply,
    mutate: (vars: UpdateStrategyMetaVars) => {
      apply.mutate({
        op: {
          kind: "updateStrategyMeta",
          ...(vars.name !== undefined && { name: vars.name }),
          ...(vars.description !== undefined && { description: vars.description }),
        },
      });
    },
    mutateAsync: async (vars: UpdateStrategyMetaVars) => {
      return apply.mutateAsync({
        op: {
          kind: "updateStrategyMeta",
          ...(vars.name !== undefined && { name: vars.name }),
          ...(vars.description !== undefined && { description: vars.description }),
        },
      });
    },
  };
}
