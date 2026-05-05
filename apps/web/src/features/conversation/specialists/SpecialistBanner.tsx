"use client";

import { useThread } from "@assistant-ui/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Microscope, Search, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SpecialistKind, SpecialistMode } from "@pathfinder/shared";
import { strategyQueryKey } from "@/lib/api/strategy";
import { listModelsQueryOptions } from "@pathfinder/shared/generated/hooks/useListModels";
import { patchSpecialistModel } from "@/lib/api/specialists";
import { cn } from "@/lib/utils/cn";

import { useExitSpecialist } from "./useEnterSpecialist";

const KIND_LABEL: Record<SpecialistKind, string> = {
  validate: "Validate",
  research: "Research",
};

const KIND_TINT: Record<SpecialistKind, string> = {
  validate: "border-primary/40 bg-primary/10 text-foreground",
  research:
    "border-secondary-foreground/20 bg-secondary text-secondary-foreground",
};

export interface SpecialistBannerProps {
  conversationId: string;
  mode: SpecialistMode;
}

export function SpecialistBanner({
  conversationId,
  mode,
}: SpecialistBannerProps) {
  const Icon = mode.kind === "validate" ? Microscope : Search;
  const isRunning = useThread((s) => s.isRunning);
  const exitMutation = useExitSpecialist(conversationId);
  const [pickerOpen, setPickerOpen] = useState(false);

  return (
    <div
      data-testid="specialist-banner"
      data-kind={mode.kind}
      className={cn(
        "sticky top-0 z-10 flex items-center gap-3 border-b px-3 py-1.5 text-xs",
        KIND_TINT[mode.kind],
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      <span className="font-medium">{KIND_LABEL[mode.kind]} mode</span>
      <span className="text-current/60" aria-hidden>·</span>

      <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            data-testid="specialist-banner-model"
            disabled={isRunning}
            className={cn(
              "rounded px-1.5 py-0.5 font-mono text-[11px] underline-offset-2 transition-colors",
              "hover:bg-black/5 dark:hover:bg-white/10",
              "disabled:cursor-not-allowed disabled:opacity-60",
            )}
          >
            {mode.modelId}
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72 p-3">
          <ModelSwapBody
            conversationId={conversationId}
            currentModelId={mode.modelId}
            isRunning={isRunning}
            onClose={() => setPickerOpen(false)}
          />
        </PopoverContent>
      </Popover>

      <div className="ml-auto">
        <Button
          type="button"
          size="sm"
          variant="outline"
          data-testid="specialist-banner-done"
          disabled={exitMutation.isPending}
          onClick={() => exitMutation.mutate()}
        >
          <X className="mr-1 size-3.5" aria-hidden /> Done
        </Button>
      </div>
    </div>
  );
}

function ModelSwapBody({
  conversationId,
  currentModelId,
  isRunning,
  onClose,
}: {
  conversationId: string;
  currentModelId: string;
  isRunning: boolean;
  onClose: () => void;
}) {
  const modelsQuery = useQuery(listModelsQueryOptions());
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState(currentModelId);

  const swapMutation = useMutation({
    mutationFn: (modelId: string) =>
      patchSpecialistModel({ conversationId, modelId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: strategyQueryKey(conversationId),
      });
      toast.success("Model swapped for upcoming turns");
      onClose();
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to swap model";
      toast.error(msg);
    },
  });

  const options = (modelsQuery.data?.models ?? []).filter(
    (m) => m.enabled !== false,
  );
  const disabled = isRunning || swapMutation.isPending;

  return (
    <div className="space-y-2">
      <p className="text-[11px] font-medium text-foreground">Session model</p>
      <p className="text-[11px] text-muted-foreground">
        Picker is disabled while a turn is in flight. The selection takes
        effect on the next turn.
      </p>
      <Select
        value={selected}
        onValueChange={setSelected}
        disabled={disabled || options.length === 0}
      >
        <SelectTrigger
          data-testid="specialist-banner-model-select"
          className="h-8 text-xs"
        >
          <SelectValue placeholder="Pick a model…" />
        </SelectTrigger>
        <SelectContent>
          {options.map((m) => (
            <SelectItem key={m.id} value={m.id}>
              <span className="font-medium">{m.name}</span>
              {m.description !== undefined && m.description !== "" ? (
                <span className="ml-1 text-[10px] text-muted-foreground">
                  {m.description}
                </span>
              ) : null}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <div className="flex justify-end gap-2 pt-1">
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onClose}
          disabled={swapMutation.isPending}
        >
          Cancel
        </Button>
        <Button
          type="button"
          size="sm"
          data-testid="specialist-banner-model-apply"
          disabled={
            disabled
            || selected === currentModelId
            || selected === ""
          }
          onClick={() => swapMutation.mutate(selected)}
        >
          {swapMutation.isPending ? "Swapping…" : "Apply"}
        </Button>
      </div>
    </div>
  );
}
