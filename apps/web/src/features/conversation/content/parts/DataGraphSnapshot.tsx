import type { GraphSnapshot } from "@pathfinder/shared";
import { Network } from "lucide-react";

export function DataGraphSnapshot({ data }: { data: GraphSnapshot }) {
  const stepCount = data.nodes.length;
  const stepLabel = stepCount === 1 ? "step" : "steps";
  return (
    <div
      data-testid="data-graph-snapshot"
      className="my-1 inline-flex items-center gap-1.5 self-start rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[11px] text-muted-foreground"
    >
      <Network className="size-3" aria-hidden />
      <span>Graph updated</span>
      <span aria-hidden>·</span>
      <span className="font-medium text-foreground">
        {stepCount} {stepLabel}
      </span>
      <span aria-hidden>·</span>
      <span>{data.geneCount.toLocaleString()} genes</span>
    </div>
  );
}
