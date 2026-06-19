import type { VariantComparison } from "@pathfinder/shared";
import { GitCompare } from "lucide-react";

export function DataVariantComparison({ data }: { data: VariantComparison }) {
  return (
    <div
      data-testid="data-variant-comparison"
      className="my-2 rounded-md border border-border bg-card px-3 py-2 text-xs"
    >
      <div className="flex items-center gap-2">
        <GitCompare className="size-3.5 text-muted-foreground" aria-hidden />
        <span className="text-sm font-medium">Variant comparison</span>
        {data.truncated === true && (
          <span className="ml-auto text-[10px] text-muted-foreground">
            large result sets — overlap is a lower bound
          </span>
        )}
      </div>

      <ul className="mt-2 space-y-1.5">
        {data.variants.map((v) => (
          <li
            key={v.label}
            className="rounded-md border border-border/60 bg-muted/20 p-2"
          >
            <div className="flex items-baseline gap-2">
              <span className="font-medium text-foreground">{v.label}</span>
              <span className="ml-auto font-mono text-[11px] text-foreground">
                {v.error != null && v.error !== "" ? "—" : `${v.geneCount} genes`}
              </span>
            </div>
            {v.error != null && v.error !== "" ? (
              <div className="mt-0.5 text-[11px] text-destructive">
                failed: {v.error}
              </div>
            ) : (
              <div className="mt-0.5 text-[11px] text-muted-foreground">
                {v.uniqueCount} unique
                {v.sampleUniqueGenes.length > 0 && (
                  <span className="font-mono"> · {v.sampleUniqueGenes.join(", ")}</span>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>

      {data.overlaps.length > 0 && (
        <dl className="mt-2 space-y-0.5 border-t border-border/50 pt-1.5">
          {data.overlaps.map((o) => (
            <div key={`${o.a}|${o.b}`} className="flex gap-2 text-[11px]">
              <dt className="text-muted-foreground">
                {o.a} vs {o.b}
              </dt>
              <dd className="ml-auto font-mono text-foreground">
                {o.shared} shared · Jaccard {o.jaccard}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
