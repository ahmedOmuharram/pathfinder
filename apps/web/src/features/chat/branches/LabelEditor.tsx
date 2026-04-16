"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { client } from "@/lib/api/client";

export function LabelEditor({
  chatId,
  checkpointId,
  currentLabel,
}: {
  chatId: string;
  checkpointId: string;
  currentLabel: string | null;
}) {
  const [value, setValue] = useState(currentLabel ?? "");
  const setLabelMutation = useMutation({
    mutationFn: async (label: string) => {
      await client({ method: "put", url: `/api/v1/chats/${chatId}/labels/${checkpointId}`, data: { label } });
    },
  });
  const deleteLabelMutation = useMutation({
    mutationFn: async () => {
      await client({ method: "delete", url: `/api/v1/chats/${chatId}/labels/${checkpointId}` });
    },
  });

  const isPending =
    setLabelMutation.isPending || deleteLabelMutation.isPending;

  async function handleSave() {
    const trimmed = value.trim();
    try {
      if (trimmed === "") {
        await deleteLabelMutation.mutateAsync();
        toast.success("Label removed");
      } else {
        await setLabelMutation.mutateAsync(trimmed);
        toast.success("Label saved");
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Label update failed";
      toast.error(message);
    }
  }

  return (
    <div className="flex items-center gap-1">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Add label..."
        className="h-7 w-32 rounded-md border border-border bg-card px-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      />
      <button
        type="button"
        onClick={() => void handleSave()}
        disabled={isPending}
        className="inline-flex h-7 items-center rounded-md border border-border bg-card px-2 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50"
        aria-label="Save label"
      >
        Save
      </button>
    </div>
  );
}
