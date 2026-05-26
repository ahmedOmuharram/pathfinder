import type { GeneSetPart } from "@pathfinder/shared";

export function DataGeneSet({ data }: { data: GeneSetPart }) {
  return (
    <div
      data-testid="data-gene-set"
      className="my-2 rounded-md border border-border bg-card px-3 py-2 text-xs"
    >
      <div className="flex items-center gap-2">
        <span className="inline-block size-1.5 rounded-full bg-emerald-500" />
        <span className="font-medium">Gene set created</span>
      </div>
      <div className="mt-1 text-muted-foreground">
        <span className="font-medium text-foreground">{data.name}</span>
        <span className="mx-1">·</span>
        <span>{data.geneCount.toLocaleString()} genes</span>
        <span className="mx-1">·</span>
        <span>{data.siteId}</span>
      </div>
    </div>
  );
}
