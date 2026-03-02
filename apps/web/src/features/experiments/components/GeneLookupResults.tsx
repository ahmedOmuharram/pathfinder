import type { RefObject } from "react";
import type { GeneSearchResult, ResolvedGene } from "@pathfinder/shared";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { GeneResultRow } from "./GeneResultRow";

const PAGE_SIZE = 50;

interface GeneLookupResultsProps {
  results: GeneSearchResult[];
  totalCount: number;
  page: number;
  loading: boolean;
  searched: boolean;
  query: string;
  organism: string;
  suggestedOrganisms: string[];
  expanded: Set<string>;
  positiveGeneIds: Set<string>;
  negativeGeneIds: Set<string>;
  resultsRef: RefObject<HTMLDivElement | null>;
  onSetQuery: (query: string) => void;
  onSetOrganism: (organism: string) => void;
  onGoToPage: (page: number) => void;
  onToggleExpand: (geneId: string) => void;
  onAddPositive: (gene: ResolvedGene) => void;
  onAddNegative: (gene: ResolvedGene) => void;
}

export function GeneLookupResults({
  results,
  totalCount,
  page,
  loading,
  searched,
  query,
  organism,
  suggestedOrganisms,
  expanded,
  positiveGeneIds,
  negativeGeneIds,
  resultsRef,
  onSetQuery,
  onSetOrganism,
  onGoToPage,
  onToggleExpand,
  onAddPositive,
  onAddNegative,
}: GeneLookupResultsProps) {
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const rangeStart = page * PAGE_SIZE + 1;
  const rangeEnd = Math.min((page + 1) * PAGE_SIZE, totalCount);

  return (
    <>
      {/* Results */}
      <div ref={resultsRef} className="max-h-72 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center py-6 text-xs text-muted-foreground">
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            Searching\u2026
          </div>
        )}

        {!loading &&
          searched &&
          results.length === 0 &&
          suggestedOrganisms.length === 0 && (
            <div className="px-3 py-5 text-center text-xs text-muted-foreground">
              <p>No genes found for &ldquo;{query}&rdquo;.</p>
              <p className="mt-1.5 text-xs">
                Try a full gene ID (e.g.{" "}
                <button
                  type="button"
                  onClick={() => onSetQuery("PF3D7_1133400")}
                  className="font-mono text-primary hover:underline"
                >
                  PF3D7_1133400
                </button>
                ), a prefix (e.g.{" "}
                <button
                  type="button"
                  onClick={() => onSetQuery("PF3D7_")}
                  className="font-mono text-primary hover:underline"
                >
                  PF3D7_
                </button>
                ), or a keyword like &ldquo;kinase&rdquo;.
              </p>
            </div>
          )}

        {!loading && searched && suggestedOrganisms.length > 0 && (
          <div className="border-b border-amber-100 bg-amber-50 px-3 py-2.5">
            <div className="text-xs font-medium text-amber-800">
              {results.length === 0
                ? `No exact organism match for "${organism}". Did you mean?`
                : `Organism "${organism}" not found exactly. Did you mean?`}
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {suggestedOrganisms.map((org) => (
                <button
                  key={org}
                  type="button"
                  onClick={() => onSetOrganism(org)}
                  className="rounded-md border border-amber-200 bg-card px-2 py-1 text-xs font-medium text-amber-900 transition hover:border-amber-400 hover:bg-amber-100"
                >
                  {org}
                </button>
              ))}
            </div>
          </div>
        )}

        {!loading && !searched && (
          <div className="px-3 py-5 text-center">
            <p className="text-xs text-muted-foreground">
              Search by gene name, ID, product, or keyword.
            </p>
            <div className="mt-2.5 flex flex-wrap justify-center gap-1.5">
              {["PF3D7_", "kinase", "falciparum"].map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => onSetQuery(example)}
                  className="rounded-full border border-border bg-card px-2.5 py-1 font-mono text-xs text-muted-foreground transition hover:border-primary/30 hover:text-primary"
                >
                  {example}
                </button>
              ))}
            </div>
            <p className="mt-2.5 text-xs leading-relaxed text-muted-foreground">
              You can also use organism abbreviations as search terms (e.g.{" "}
              <span className="font-mono">pf3d7</span> for <em>P. falciparum 3D7</em>)
              \u2014 the search will automatically match genes from the right organism.
            </p>
          </div>
        )}

        {!loading &&
          results.map((gene) => (
            <GeneResultRow
              key={gene.geneId}
              gene={gene}
              isExpanded={expanded.has(gene.geneId)}
              onToggleExpand={onToggleExpand}
              positiveGeneIds={positiveGeneIds}
              negativeGeneIds={negativeGeneIds}
              onAddPositive={onAddPositive}
              onAddNegative={onAddNegative}
            />
          ))}
      </div>

      {/* Footer -- pagination */}
      {searched && totalCount > 0 && (
        <div className="flex items-center justify-between border-t border-border px-3 py-1.5">
          <span className="text-xs text-muted-foreground">
            {rangeStart}\u2013{rangeEnd} of {totalCount}
          </span>
          {totalPages > 1 && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onGoToPage(page - 1)}
                disabled={page === 0 || loading}
                className="flex items-center rounded border border-border bg-card p-0.5 text-muted-foreground transition hover:bg-muted disabled:opacity-30"
                aria-label="Previous page"
              >
                <ChevronLeft className="h-3 w-3" />
              </button>
              <span className="min-w-[3rem] text-center text-xs text-muted-foreground">
                {page + 1} / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => onGoToPage(page + 1)}
                disabled={page >= totalPages - 1 || loading}
                className="flex items-center rounded border border-border bg-card p-0.5 text-muted-foreground transition hover:bg-muted disabled:opacity-30"
                aria-label="Next page"
              >
                <ChevronRight className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
