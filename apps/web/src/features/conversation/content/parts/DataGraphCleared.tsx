import type { GraphCleared } from "@pathfinder/shared";
import { Trash2 } from "lucide-react";

export function DataGraphCleared({ data }: { data: GraphCleared }) {
  return (
    <div
      data-testid="data-graph-cleared"
      className="my-1 inline-flex items-center gap-1.5 self-start rounded-md border border-border bg-muted/30 px-2 py-0.5 text-[11px] text-muted-foreground"
    >
      <Trash2 className="size-3" aria-hidden />
      <span className="font-medium text-foreground">Strategy cleared</span>
      {data.reason !== null && data.reason !== undefined && data.reason !== "" && (
        <>
          <span aria-hidden>·</span>
          <span>{data.reason}</span>
        </>
      )}
    </div>
  );
}
