"use client";

import { useState } from "react";
import { parseAsString, useQueryState } from "nuqs";
import { toast } from "sonner";
import { client } from "@/lib/api/client";

interface ForkResponse {
  newCheckpointId: string;
}

export function ForkButton({
  chatId,
  checkpointId,
}: {
  chatId: string;
  checkpointId: string;
}) {
  const [isPending, setIsPending] = useState(false);
  const [, setActiveBranch] = useQueryState("branch", parseAsString);

  async function handleFork() {
    setIsPending(true);
    try {
      const result = await client<ForkResponse>({
        method: "post",
        url: `/api/v1/conversations/${chatId}/fork`,
        data: { fromCheckpointId: checkpointId },
      });
      toast.success("Branch created");
      void setActiveBranch(result.data.newCheckpointId);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Fork failed";
      toast.error(message);
    } finally {
      setIsPending(false);
    }
  }

  return (
    <button
      type="button"
      onClick={() => void handleFork()}
      disabled={isPending}
      className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50"
      aria-label="Fork from this checkpoint"
    >
      ⎇ Fork
    </button>
  );
}
