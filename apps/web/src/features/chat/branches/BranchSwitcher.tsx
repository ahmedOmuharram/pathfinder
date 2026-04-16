"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { client } from "@/lib/api/client";
import type { CheckpointNode } from "@pathfinder/shared/generated/types/CheckpointNode";
import { BranchTree } from "./BranchTree";

export function BranchSwitcher({ chatId }: { chatId: string }) {
  const [open, setOpen] = useState(false);
  const { data: checkpoints = [] } = useQuery({
    queryKey: ["checkpoints", chatId],
    queryFn: async () => {
      const resp = await client<CheckpointNode[]>({
        method: "get",
        url: `/api/v1/chats/${chatId}/checkpoints`,
      });
      return resp.data;
    },
    enabled: chatId !== "",
  });

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        aria-label="Branches"
      >
        ⎇ Branches
        <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-muted px-1 text-[10px] font-semibold leading-none text-muted-foreground">
          {checkpoints.length}
        </span>
      </button>
      {open && (
        <div className="absolute inset-y-0 right-0 z-40 flex w-80 flex-col border-l border-border bg-card shadow-lg">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <span className="text-xs font-semibold text-foreground">
              Branch Tree
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="inline-flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              aria-label="Close branch panel"
            >
              ✕
            </button>
          </div>
          <div className="min-h-0 flex-1">
            <BranchTree chatId={chatId} />
          </div>
        </div>
      )}
    </>
  );
}
