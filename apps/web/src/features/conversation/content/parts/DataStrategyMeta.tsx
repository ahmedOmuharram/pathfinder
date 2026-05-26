import type { StrategyMeta } from "@pathfinder/shared";
import { BookmarkCheck, FileChartColumn } from "lucide-react";

export function DataStrategyMeta({ data }: { data: StrategyMeta }) {
  const Icon = data.isSaved ? BookmarkCheck : FileChartColumn;
  return (
    <div
      data-testid="data-strategy-meta"
      className="my-1 inline-flex items-center gap-1.5 self-start rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[11px] text-muted-foreground"
    >
      <Icon className="size-3" aria-hidden />
      <span className="font-medium text-foreground">{data.name}</span>
      <span aria-hidden>·</span>
      <span>{data.estimatedSize.toLocaleString()} genes</span>
      {data.isSaved && (
        <>
          <span aria-hidden>·</span>
          <span>saved</span>
        </>
      )}
    </div>
  );
}
