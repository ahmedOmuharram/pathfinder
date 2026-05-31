import type { EnrichmentResult, EnrichmentResultsChunk } from "@pathfinder/shared";
import { EnrichmentSection } from "@/features/analysis";

export function DataEnrichmentResults({ data }: { data: EnrichmentResultsChunk }) {
  const results = data.results as unknown as EnrichmentResult[];
  return (
    <div
      data-testid="data-enrichment-results"
      className="my-2 rounded-md border border-border bg-card p-3"
    >
      <div className="mb-2 flex items-center justify-between text-xs">
        <div>
          <span className="font-medium">Enrichment</span>
          <span className="mx-1 text-muted-foreground">·</span>
          <span className="text-muted-foreground">{data.geneSetName}</span>
          <span className="mx-1 text-muted-foreground">·</span>
          <span className="text-muted-foreground">{data.geneCount} genes</span>
        </div>
        {data.downloads != null && typeof data.downloads["csv"] === "string" ? (
          <a
            className="text-primary hover:underline"
            href={data.downloads["csv"]}
            target="_blank"
            rel="noreferrer"
          >
            Download CSV
          </a>
        ) : null}
      </div>
      <EnrichmentSection results={results} />
    </div>
  );
}
