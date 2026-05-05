"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "@tanstack/react-form";
import { AnimatePresence, motion } from "motion/react";
import { X, Zap } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  strategyQueryKey,
  strategyQueryOptions,
} from "@/lib/api/strategy";
import {
  LauncherPreconditionError,
  postOptimizeLaunch,
  type OptimizeLaunchRequest,
} from "@/lib/api/launchers";
import { listModelsQueryOptions } from "@pathfinder/shared/generated/hooks/useListModels";
import { cn } from "@/lib/utils/cn";

import {
  BudgetField,
  CriterionField,
  ModelField,
  ParamPicker,
  StepPicker,
} from "./optimizeFormFields";
import type { LauncherForm, OptimizeFormValues } from "./optimizeFormTypes";

export interface OptimizeLauncherFormProps {
  open: boolean;
  conversationId: string;
  onClose: () => void;
}

const DEFAULT_BUDGET = 20;

export function OptimizeLauncherForm({
  open,
  conversationId,
  onClose,
}: OptimizeLauncherFormProps) {
  const queryClient = useQueryClient();
  const detailQuery = useQuery(strategyQueryOptions(conversationId));
  const modelsQuery = useQuery(listModelsQueryOptions());

  const steps = detailQuery.data?.steps ?? [];
  const focusedStep = steps[steps.length - 1];

  const launchMutation = useMutation({
    mutationFn: (body: OptimizeLaunchRequest) =>
      postOptimizeLaunch(conversationId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: strategyQueryKey(conversationId),
      });
      void queryClient.invalidateQueries({
        queryKey: ["conversations", conversationId, "messages"],
      });
      onClose();
      toast.success("Optimization started");
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof LauncherPreconditionError
          ? `Cannot start optimization: ${err.detail}`
          : err instanceof Error
            ? err.message
            : "Failed to start optimization";
      toast.error(msg);
    },
  });

  const form = useForm({
    defaultValues: {
      stepId: focusedStep?.id != null ? Number(focusedStep.id) : null,
      paramKeys: [] as string[],
      criterion: "",
      budget: DEFAULT_BUDGET,
      modelId: "",
    } as OptimizeFormValues,
    onSubmit: ({ value }) => {
      if (value.stepId === null) {
        toast.error("Pick a step to optimize");
        return;
      }
      if (value.paramKeys.length === 0) {
        toast.error("Pick at least one parameter to tune");
        return;
      }
      if (value.criterion.trim() === "") {
        toast.error("Describe what you're optimizing for");
        return;
      }
      launchMutation.mutate({
        stepId: value.stepId,
        paramKeys: value.paramKeys,
        criterion: value.criterion.trim(),
        budget: value.budget,
        modelId: value.modelId === "" ? null : value.modelId,
      });
    },
  });

  // Render-time sync: if the focused step changes while the form is open and
  // the user hasn't picked one, adopt the new default. The previous step id is
  // tracked in local state so we don't fight the user once they choose.
  const [lastFocusedId, setLastFocusedId] = useState<string | null>(
    focusedStep?.id ?? null,
  );
  const currentFocusedId = focusedStep?.id ?? null;
  if (currentFocusedId !== lastFocusedId) {
    setLastFocusedId(currentFocusedId);
    if (form.state.values.stepId === null && currentFocusedId !== null) {
      form.setFieldValue("stepId", Number(currentFocusedId));
    }
  }

  if (!open) return null;

  const currentStep = steps.find(
    (s) => Number(s.id) === form.state.values.stepId,
  );

  const launcherForm: LauncherForm = {
    store: form.store,
    setStepId: (v) => form.setFieldValue("stepId", v),
    setParamKeys: (v) => form.setFieldValue("paramKeys", v),
    setCriterion: (v) => form.setFieldValue("criterion", v),
    setBudget: (v) => form.setFieldValue("budget", v),
    setModelId: (v) => form.setFieldValue("modelId", v),
  };

  return (
    <AnimatePresence>
      <motion.div
        key="optimize-launcher"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 16 }}
        transition={{ duration: 0.18 }}
        data-testid="optimize-launcher-form"
        className={cn(
          "absolute bottom-full left-0 right-0 z-30 mb-2",
          "rounded-lg border border-border bg-popover",
          "shadow-[var(--shadow-float)]",
        )}
      >
        <div className="flex items-center justify-between border-b border-border/60 px-3 py-2">
          <div className="flex items-center gap-2 text-sm">
            <Zap className="size-4 text-amber-500" aria-hidden />
            <span className="font-medium">Optimize parameters</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            onClick={onClose}
            aria-label="Cancel"
            data-testid="optimize-launcher-cancel"
          >
            <X className="size-3.5" />
          </Button>
        </div>

        <form
          className="space-y-3 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void form.handleSubmit();
          }}
        >
          <StepPicker form={launcherForm} steps={steps} />
          <ParamPicker
            form={launcherForm}
            siteId={detailQuery.data?.siteId ?? ""}
            recordType={detailQuery.data?.recordType ?? ""}
            stepSearchName={currentStep?.searchName ?? ""}
          />
          <CriterionField form={launcherForm} />
          <BudgetField form={launcherForm} />
          <ModelField
            form={launcherForm}
            options={modelsQuery.data?.models ?? []}
          />

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onClose}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={launchMutation.isPending}
              data-testid="optimize-launcher-submit"
            >
              {launchMutation.isPending ? "Launching..." : "Launch"}
            </Button>
          </div>
        </form>
      </motion.div>
    </AnimatePresence>
  );
}
