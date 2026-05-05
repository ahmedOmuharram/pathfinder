"use client";

import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { strategyQueryKey } from "@/lib/api/strategy";
import { taskStatusOptions } from "@/lib/api/tasks";
import { useUpdateStepMutation } from "@/features/strategy/mutations/useUpdateStepMutation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

const bestSchema = z.object({
  variantId: z.string().optional(),
  params: z.record(z.string(), z.unknown()),
});

const sweepResultSchema = z
  .object({ best: bestSchema.nullable() })
  .passthrough();

function paramsToStrings(
  params: Record<string, unknown>,
): Record<string, string | string[]> {
  const out: Record<string, string | string[]> = {};
  for (const [k, v] of Object.entries(params)) {
    if (Array.isArray(v)) {
      out[k] = v.map(String);
    } else if (v == null) {
      continue;
    } else {
      out[k] = String(v);
    }
  }
  return out;
}

export function OptimizeApplyButton({
  conversationId,
  taskId,
  localStepId,
}: {
  conversationId: string;
  taskId: string;
  /** Local AST step id from the launch part — what useUpdateStepMutation expects. */
  localStepId: string;
}) {
  const queryClient = useQueryClient();
  const taskQuery = useQuery(taskStatusOptions(conversationId, taskId));
  const updateStep = useUpdateStepMutation(conversationId);

  if (taskQuery.data === undefined) return null;
  if (taskQuery.data.status !== "complete") return null;

  const parsed = sweepResultSchema.safeParse(taskQuery.data.result);
  if (!parsed.success || parsed.data.best === null) return null;
  const best = parsed.data.best;

  const onApply = (): void => {
    void updateStep
      .mutateAsync({
        stepId: localStepId,
        patch: { parameters: paramsToStrings(best.params) },
      })
      .then(() => {
        void queryClient.invalidateQueries({
          queryKey: strategyQueryKey(conversationId),
        });
        toast.success("Best config applied to step");
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : "Failed to apply";
        toast.error(msg);
      });
  };

  return (
    <div className="mt-2 flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1.5 text-[11px] dark:border-emerald-800 dark:bg-emerald-950">
      <Sparkles className="size-3.5 text-emerald-600 dark:text-emerald-400" />
      <span className="font-medium">Sweep complete</span>
      <span className="text-muted-foreground">·</span>
      <span className="text-muted-foreground truncate">
        Best variant{best.variantId !== undefined ? ` ${best.variantId}` : ""}
      </span>
      <Button
        type="button"
        size="sm"
        variant="default"
        className="ml-auto h-6 px-2 text-[11px]"
        disabled={updateStep.isPending}
        data-testid="optimize-apply-best"
        onClick={onApply}
      >
        {updateStep.isPending ? "Applying…" : "Apply best config"}
      </Button>
    </div>
  );
}
