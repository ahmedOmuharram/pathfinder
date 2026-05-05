"use client";

import {
  computeDeleteChoices,
  type DeleteResolution,
} from "@/features/strategy/operations";
import { useStrategyCacheUtils } from "@/lib/api/strategy";
import { useApplyOperation } from "@/features/strategy/mutations/useApplyOperation";
import { useGraphActionConfirm } from "./useGraphActionConfirm";

interface DeleteManyOptions {
  /** Bypass the confirm dialog (for orphan removal where user already opted in). */
  skipConfirm?: boolean | undefined;
}

export function useDeleteOperation(conversationId: string): {
  requestDelete: (stepId: string) => void;
  requestDeleteMany: (stepIds: string[], options?: DeleteManyOptions) => void;
  dialogProps: ReturnType<typeof useGraphActionConfirm<DeleteResolution>>["dialogProps"];
} {
  const cache = useStrategyCacheUtils();
  const apply = useApplyOperation(conversationId);
  const confirm = useGraphActionConfirm<DeleteResolution>();

  const applyDeleteOp = (stepId: string, resolution: DeleteResolution): void => {
    apply.mutate({ op: { kind: "deleteStep", stepId, resolution } });
  };

  const requestDelete = (stepId: string): void => {
    const current = cache.get(conversationId);
    if (!current) return;
    const choices = computeDeleteChoices(current.steps, stepId);
    if (choices.length === 0) return;

    if (choices.length === 1) {
      applyDeleteOp(stepId, choices[0]!.resolution);
      return;
    }

    const target = current.steps.find((s) => s.id === stepId);
    confirm.confirmAction({
      title: "Delete this step?",
      subtitle: target?.displayName ?? stepId,
      choices,
      onResolve: (resolution) => {
        applyDeleteOp(stepId, resolution);
      },
      confirmLabel: "Delete",
    });
  };

  const requestDeleteMany = (
    stepIds: string[],
    options?: DeleteManyOptions,
  ): void => {
    if (stepIds.length === 0) return;
    if (stepIds.length === 1) {
      requestDelete(stepIds[0]!);
      return;
    }
    const current = cache.get(conversationId);
    if (!current) return;

    const fireSequential = (): void => {
      for (const id of stepIds) {
        const choices = computeDeleteChoices(current.steps, id);
        const def =
          choices.find((c) => c.isDefault)?.resolution ??
          choices[0]?.resolution;
        if (def !== undefined) applyDeleteOp(id, def);
      }
    };

    if (options?.skipConfirm === true) {
      fireSequential();
      return;
    }

    const willDelete = current.steps
      .map((s) => s.id)
      .filter((id) => stepIds.includes(id));
    confirm.confirmAction({
      title: `Delete ${stepIds.length} steps?`,
      subtitle:
        "Each step uses its safe default (collapse combine where applicable).",
      choices: [
        {
          resolution: "delete-subtree",
          title: `Delete ${stepIds.length} steps`,
          description:
            "Apply the default resolution per step (combine collapses keep siblings reconnected).",
          isDefault: true,
          willDelete,
          willOrphan: [],
        },
      ],
      onResolve: () => {
        fireSequential();
      },
      confirmLabel: "Delete",
    });
  };

  return {
    requestDelete,
    requestDeleteMany,
    dialogProps: confirm.dialogProps,
  };
}
