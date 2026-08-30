import type { EnrichmentResult, EnrichmentResultsChunk } from "@pathfinder/shared";
import { EnrichmentSection } from "@/features/analysis";
import { Figure } from "@/lib/components/thread/Figure";

export function DataEnrichmentResults({ data }: { data: EnrichmentResultsChunk }) {
  const results = data.results as unknown as EnrichmentResult[];
  const csv = data.downloads?.["csv"];
  return (
    <Figure
      testId="data-enrichment-results"
      title="Enrichment"
      caption={`${results.length.toLocaleString()} terms, ${data.geneCount.toLocaleString()} genes analyzed`}
    >
      <div>
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className="text-muted-foreground">{data.geneSetName}</span>
          {typeof csv === "string" ? (
            <a
              className="text-primary hover:underline"
              href={csv}
              target="_blank"
              rel="noreferrer"
            >
              Download CSV
            </a>
          ) : null}
        </div>
        <EnrichmentSection results={results} />
      </div>
    </Figure>
  );
}
