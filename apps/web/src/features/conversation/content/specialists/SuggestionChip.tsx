"use client";

import type { SpecialistKind } from "@pathfinder/shared";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";

import { enterSpecialist } from "@/lib/api/specialists";
import { cn } from "@/lib/utils/cn";

const KIND_LABEL: Record<SpecialistKind, string> = {
  validate: "Want to /validate this?",
  research: "Want to /research this?",
};

const KIND_TINT: Record<SpecialistKind, string> = {
  validate: "border-emerald-300 text-emerald-800 hover:bg-emerald-50 dark:text-emerald-200",
  research: "border-sky-300 text-sky-800 hover:bg-sky-50 dark:text-sky-200",
};

export function SuggestionChip({
  kind,
  conversationId,
  onEntered,
}: {
  kind: SpecialistKind;
  conversationId: string;
  onEntered?: () => void;
}) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => enterSpecialist({ conversationId, kind }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["conversations", conversationId, "messages"],
      });
      void queryClient.invalidateQueries({
        queryKey: ["conversations", conversationId, "detail"],
      });
      onEntered?.();
    },
    onError: (err) => {
      toast.error(
        err instanceof Error
          ? err.message
          : `Failed to enter /${kind}`,
      );
    },
  });

  return (
    <button
      type="button"
      data-testid="data-specialist-suggestion-chip"
      data-kind={kind}
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      className={cn(
        "my-1 inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-[11px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        KIND_TINT[kind],
      )}
    >
      <Sparkles className="size-3" aria-hidden />
      <span>{KIND_LABEL[kind]}</span>
    </button>
  );
}
