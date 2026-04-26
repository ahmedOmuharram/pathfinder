"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import type { Step, Strategy } from "@pathfinder/shared";
import {
  conversationDetailKey,
  patchConversationStep,
  type StepPatchArgs,
} from "@/lib/api/conversations";
import { toUserMessage } from "@/lib/api/errors";
import { useSessionStore } from "@/state/useSessionStore";

export interface UpdateStepVars {
  stepId: string;
  patch: Partial<Step>;
}

interface UpdateStepContext {
  snapshot: Strategy | null;
}

export const STEP_PATCH_MUTATION_KEY = ["strategy", "step-patch"] as const;

function buildPatchArgs(patch: Partial<Step>): StepPatchArgs {
  const out: StepPatchArgs = {};
  if (patch.parameters !== undefined && patch.parameters !== null) {
    out.parameters = patch.parameters as Record<string, unknown>;
  }
  if (patch.operator !== undefined && patch.operator !== null) {
    out.operator = patch.operator;
  }
  if (patch.displayName !== undefined) {
    out.displayName = patch.displayName;
  }
  if (patch.colocationParams !== undefined) {
    out.colocationParams = patch.colocationParams;
  }
  if (patch.searchName !== undefined && patch.searchName !== null) {
    out.searchName = patch.searchName;
  }
  return out;
}

export function useUpdateStepMutation(conversationId: string) {
  const queryClient = useQueryClient();
  const siteId = useSessionStore((s) => s.selectedSite);
  return useMutation<Step, Error, UpdateStepVars, UpdateStepContext>({
    mutationKey: [...STEP_PATCH_MUTATION_KEY, conversationId],
    onMutate: ({ stepId, patch }) => {
      const key = conversationDetailKey(conversationId);
      const snapshot = queryClient.getQueryData<Strategy>(key) ?? null;
      if (snapshot !== null) {
        queryClient.setQueryData<Strategy>(key, {
          ...snapshot,
          steps: snapshot.steps.map((s) =>
            s.id === stepId ? { ...s, ...patch } : s,
          ),
        });
      }
      return { snapshot };
    },
    mutationFn: async ({ stepId, patch }) => {
      return await patchConversationStep(
        conversationId,
        stepId,
        buildPatchArgs(patch),
        siteId,
      );
    },
    onSuccess: (updatedStep, vars) => {
      const key = conversationDetailKey(conversationId);
      queryClient.setQueryData<Strategy>(key, (current) => {
        if (current === undefined) return current;
        return {
          ...current,
          steps: current.steps.map((s) =>
            s.id === vars.stepId ? updatedStep : s,
          ),
        };
      });
    },
    onError: (err, _vars, context) => {
      if (context?.snapshot !== undefined && context.snapshot !== null) {
        queryClient.setQueryData(
          conversationDetailKey(conversationId),
          context.snapshot,
        );
      }
      toast.error(toUserMessage(err, "Step update failed"));
    },
  });
}
