"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import type { SpecialistKind } from "@pathfinder/shared";
import {
  enterSpecialist,
  exitSpecialist,
  SpecialistEnterRefusedError,
  type SpecialistEnterResponse,
  type SpecialistExitResponse,
} from "@/lib/api/specialists";
import { conversationDetailKey } from "@/lib/api/conversations";

interface EnterArgs {
  kind: SpecialistKind;
  arg?: string;
  modelId?: string;
}

export function useEnterSpecialist(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation<SpecialistEnterResponse, Error, EnterArgs>({
    mutationFn: ({ kind, arg, modelId }) =>
      enterSpecialist({
        conversationId,
        kind,
        ...(arg !== undefined && { arg }),
        ...(modelId !== undefined && { modelId }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: conversationDetailKey(conversationId),
      });
      void queryClient.invalidateQueries({
        queryKey: ["conversations", conversationId, "messages"],
      });
    },
    onError: (err) => {
      if (err instanceof SpecialistEnterRefusedError) {
        toast.error(`Could not enter specialist: ${err.message}`);
        return;
      }
      toast.error(`Failed to enter specialist mode: ${err.message}`);
    },
  });
}

export function useExitSpecialist(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation<SpecialistExitResponse, Error>({
    mutationFn: () => exitSpecialist(conversationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: conversationDetailKey(conversationId),
      });
      void queryClient.invalidateQueries({
        queryKey: ["conversations", conversationId, "messages"],
      });
    },
    onError: (err) => {
      toast.error(`Failed to exit specialist mode: ${err.message}`);
    },
  });
}
