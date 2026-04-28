"use client";

import { useState } from "react";
import { useMutation, useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import { Bookmark } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { client } from "@/lib/api/client";
import { conversationListOptions } from "@/lib/api/conversations";
import { conversationDetailKey } from "@/lib/api/conversations";
import { toUserMessage } from "@/lib/api/errors";
import { QueryBoundary } from "@/lib/components/QueryBoundary";
import { cn } from "@/lib/utils/cn";

const OPERATORS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "INTERSECT", label: "INTERSECT (A ∩ B)" },
  { value: "UNION", label: "UNION (A ∪ B)" },
  { value: "MINUS", label: "MINUS (A − B)" },
  { value: "RMINUS", label: "RMINUS (B − A)" },
];

interface InsertSavedDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  conversationId: string;
  siteId: string;
  /** The step that the inserted saved strategy will combine with. */
  targetStepId: string;
}

export function InsertSavedDialog(props: InsertSavedDialogProps) {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent
        data-testid="insert-saved-dialog"
        className="sm:max-w-2xl"
      >
        <DialogHeader>
          <DialogTitle>Insert saved strategy</DialogTitle>
          <DialogDescription>
            Pick a saved strategy from your library and choose how it should
            combine with the target step. The inserted strategy renders as a
            collapsed container in the strategy view.
          </DialogDescription>
        </DialogHeader>
        <QueryBoundary>
          <InsertSavedDialogBody {...props} />
        </QueryBoundary>
      </DialogContent>
    </Dialog>
  );
}

interface InsertSavedRequest {
  conversationId: string;
  siteId: string;
  targetStepId: string;
  savedWdkStrategyId: number;
  operator: string;
}

interface InsertSavedResponse {
  wdkStrategyId: number;
  insertedSavedWdkStrategyId: number;
  insertedSavedName: string;
  combineStepId: string;
}

async function callInsertSavedEndpoint(
  args: InsertSavedRequest,
): Promise<InsertSavedResponse> {
  const resp = await client<InsertSavedResponse>({
    method: "post",
    url: `/api/v1/conversations/${args.conversationId}/insert-saved`,
    params: { siteId: args.siteId },
    data: {
      targetStepId: args.targetStepId,
      savedWdkStrategyId: args.savedWdkStrategyId,
      operator: args.operator,
    },
  });
  return resp.data;
}

function InsertSavedDialogBody({
  conversationId,
  siteId,
  targetStepId,
  onOpenChange,
}: InsertSavedDialogProps) {
  const queryClient = useQueryClient();
  const { data: convs } = useSuspenseQuery(conversationListOptions(siteId));
  const saved = convs
    .filter(
      (c) => c.isSaved === true && c.wdkStrategyId != null && c.id !== conversationId,
    )
    .sort((a, b) => a.name.localeCompare(b.name));

  const [filter, setFilter] = useState("");
  const [pickedId, setPickedId] = useState<number | null>(null);
  const [operator, setOperator] = useState("INTERSECT");

  const filtered =
    filter.trim() === ""
      ? saved
      : saved.filter((c) =>
          c.name.toLowerCase().includes(filter.trim().toLowerCase()),
        );

  const insert = useMutation({
    mutationFn: () =>
      callInsertSavedEndpoint({
        conversationId,
        siteId,
        targetStepId,
        savedWdkStrategyId: pickedId ?? 0,
        operator,
      }),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({
        queryKey: conversationDetailKey(conversationId),
      });
      void queryClient.invalidateQueries({
        queryKey: ["conversations", "list", siteId],
      });
      toast.success("Saved strategy inserted", {
        description: data.insertedSavedName,
      });
      onOpenChange(false);
    },
    onError: (e) =>
      toast.error("Insert failed", { description: toUserMessage(e) }),
  });

  return (
    <div className="space-y-3">
      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter saved strategies…"
        className="h-8 w-full rounded-md border border-input bg-transparent px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
      />
      <div className="max-h-72 overflow-auto rounded-md border border-border">
        {filtered.length === 0 ? (
          <p className="p-4 text-center text-sm text-muted-foreground">
            No saved strategies yet — save one from a step&apos;s &ldquo;Save as
            reusable&rdquo; menu first.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {filtered.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => setPickedId(c.wdkStrategyId ?? null)}
                  className={cn(
                    "flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-muted/50",
                    pickedId === c.wdkStrategyId && "bg-primary/10",
                  )}
                  data-testid={`insert-saved-pick-${c.wdkStrategyId}`}
                >
                  <Bookmark
                    className="mt-0.5 size-3 shrink-0 text-primary"
                    aria-hidden
                  />
                  <span className="flex-1">
                    <span className="block text-sm font-medium">{c.name}</span>
                    <span className="block text-xs text-muted-foreground">
                      {(c.stepCount ?? 0)}{" "}
                      {(c.stepCount ?? 0) === 1 ? "step" : "steps"}
                      {c.recordType != null ? ` · ${c.recordType}` : ""}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex items-center gap-2">
        <label
          htmlFor="insert-saved-operator"
          className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
        >
          Operator
        </label>
        <select
          id="insert-saved-operator"
          value={operator}
          onChange={(e) => setOperator(e.target.value)}
          className="h-8 flex-1 rounded-md border border-input bg-transparent px-2 text-sm outline-none focus:ring-2 focus:ring-ring"
        >
          {OPERATORS.map((op) => (
            <option key={op.value} value={op.value}>
              {op.label}
            </option>
          ))}
        </select>
      </div>
      <DialogFooter>
        <Button
          type="button"
          variant="ghost"
          onClick={() => onOpenChange(false)}
          disabled={insert.isPending}
        >
          Cancel
        </Button>
        <Button
          type="button"
          onClick={() => insert.mutate()}
          disabled={pickedId == null || insert.isPending}
          data-testid="insert-saved-confirm"
        >
          {insert.isPending ? "Sending…" : "Insert"}
        </Button>
      </DialogFooter>
    </div>
  );
}
