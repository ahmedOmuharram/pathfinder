import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  searchGenes,
  type GeneSearchResult,
  type ResolvedGene,
} from "@/lib/api/client";
import {
  Search,
  Loader2,
  Plus,
  Minus,
  Check,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  X,
  Lightbulb,
} from "lucide-react";

const PAGE_SIZE = 50;

function toResolvedGene(g: GeneSearchResult): ResolvedGene {
  return {
    geneId: g.geneId,
    displayName: g.displayName,
    organism: g.organism,
    product: g.product,
    geneName: g.geneName ?? "",
    geneType: g.geneType ?? "",
    location: g.location ?? "",
  };
}

interface GeneLookupPanelProps {
  siteId: string;
  positiveGeneIds: Set<string>;
  negativeGeneIds: Set<string>;
  onAddPositive: (gene: ResolvedGene) => void;
  onAddNegative: (gene: ResolvedGene) => void;
  onClose: () => void;
}

export function GeneLookupPanel({
  siteId,
  positiveGeneIds,
  negativeGeneIds,
  onAddPositive,
  onAddNegative,
  onClose,
}: GeneLookupPanelProps) {
  const [query, setQuery] = useState("");
  const [organism, setOrganism] = useState("");
  const [results, setResults] = useState<GeneSearchResult[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(0);
  const [suggestedOrganisms, setSuggestedOrganisms] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const resultsRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const rangeStart = page * PAGE_SIZE + 1;
  const rangeEnd = Math.min((page + 1) * PAGE_SIZE, totalCount);

  const fetchPage = useCallback(
    async (q: string, org: string, pageNum: number) => {
      if (!q.trim()) {
        setResults([]);
        setTotalCount(0);
        setSuggestedOrganisms([]);
        setSearched(false);
        return;
      }
      setLoading(true);
      setSearched(true);
      try {
        const resp = await searchGenes(
          siteId,
          q.trim(),
          org || null,
          PAGE_SIZE,
          pageNum * PAGE_SIZE,
        );
        setResults(resp.results);
        setTotalCount(resp.totalCount);
        setSuggestedOrganisms(resp.suggestedOrganisms ?? []);
      } catch {
        if (pageNum === 0) {
          setResults([]);
          setTotalCount(0);
          setSuggestedOrganisms([]);
        }
      } finally {
        setLoading(false);
      }
    },
    [siteId],
  );

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPage(0);
      fetchPage(query, organism, 0);
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, organism, fetchPage]);

  const goToPage = useCallback(
    (p: number) => {
      setPage(p);
      setExpanded(new Set());
      fetchPage(query, organism, p);
      resultsRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    },
    [query, organism, fetchPage],
  );

  const toggleExpand = (geneId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(geneId)) next.delete(geneId);
      else next.add(geneId);
      return next;
    });
  };

  const searchHint = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    if (/^[a-z]{2,6}\d/i.test(q) && !q.includes("_")) {
      return "Looks like a gene ID prefix — results include wildcard matches across the database.";
    }
    if (q.includes("_") && /^[a-z0-9]+_/i.test(q)) {
      return "Searching by gene ID prefix — matching genes will appear at the top.";
    }
    return null;
  }, [query]);

  return (
    <div className="rounded-lg border border-indigo-200 bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-indigo-100 px-3 py-2">
        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-indigo-700">
          <Search className="h-3.5 w-3.5" />
          Find Gene IDs
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-0.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Search inputs */}
      <div className="space-y-2 border-b border-slate-100 p-3">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Gene name, ID prefix, product, or keyword…"
              className="w-full rounded-md border border-slate-200 py-1.5 pl-7 pr-2 text-[12px] outline-none placeholder:text-slate-400 focus:border-indigo-300"
              autoFocus
            />
          </div>
        </div>
        <div>
          <input
            type="text"
            value={organism}
            onChange={(e) => setOrganism(e.target.value)}
            placeholder="Filter by organism (optional)…"
            className="w-full rounded-md border border-slate-200 px-2.5 py-1.5 text-[12px] outline-none placeholder:text-slate-400 focus:border-indigo-300"
          />
        </div>
        {searchHint && (
          <div className="flex items-start gap-1.5 rounded bg-indigo-50/80 px-2.5 py-1.5">
            <Lightbulb className="mt-0.5 h-3 w-3 shrink-0 text-indigo-400" />
            <span className="text-[10px] text-indigo-600">{searchHint}</span>
          </div>
        )}
      </div>

      {/* Results */}
      <div ref={resultsRef} className="max-h-72 overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center py-6 text-[11px] text-slate-400">
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            Searching…
          </div>
        )}

        {!loading &&
          searched &&
          results.length === 0 &&
          suggestedOrganisms.length === 0 && (
            <div className="px-3 py-5 text-center text-[11px] text-slate-400">
              <p>No genes found for &ldquo;{query}&rdquo;.</p>
              <p className="mt-1.5 text-[10px]">
                Try a full gene ID (e.g.{" "}
                <button
                  type="button"
                  onClick={() => setQuery("PF3D7_1133400")}
                  className="font-mono text-indigo-500 hover:underline"
                >
                  PF3D7_1133400
                </button>
                ), a prefix (e.g.{" "}
                <button
                  type="button"
                  onClick={() => setQuery("PF3D7_")}
                  className="font-mono text-indigo-500 hover:underline"
                >
                  PF3D7_
                </button>
                ), or a keyword like &ldquo;kinase&rdquo;.
              </p>
            </div>
          )}

        {!loading && searched && suggestedOrganisms.length > 0 && (
          <div className="border-b border-amber-100 bg-amber-50 px-3 py-2.5">
            <div className="text-[11px] font-medium text-amber-800">
              {results.length === 0
                ? `No exact organism match for "${organism}". Did you mean?`
                : `Organism "${organism}" not found exactly. Did you mean?`}
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {suggestedOrganisms.map((org) => (
                <button
                  key={org}
                  type="button"
                  onClick={() => setOrganism(org)}
                  className="rounded-md border border-amber-200 bg-white px-2 py-1 text-[11px] font-medium text-amber-900 transition hover:border-amber-400 hover:bg-amber-100"
                >
                  {org}
                </button>
              ))}
            </div>
          </div>
        )}

        {!loading && !searched && (
          <div className="px-3 py-5 text-center">
            <p className="text-[11px] text-slate-500">
              Search by gene name, ID, product, or keyword.
            </p>
            <div className="mt-2.5 flex flex-wrap justify-center gap-1.5">
              {["PF3D7_", "kinase", "falciparum"].map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setQuery(example)}
                  className="rounded-full border border-slate-200 bg-white px-2.5 py-1 font-mono text-[10px] text-slate-500 transition hover:border-indigo-300 hover:text-indigo-600"
                >
                  {example}
                </button>
              ))}
            </div>
            <p className="mt-2.5 text-[10px] leading-relaxed text-slate-400">
              You can also use organism abbreviations as search terms (e.g.{" "}
              <span className="font-mono">pf3d7</span> for <em>P. falciparum 3D7</em>) —
              the search will automatically match genes from the right organism.
            </p>
          </div>
        )}

        {!loading &&
          results.map((gene) => {
            const isExpanded = expanded.has(gene.geneId);
            return (
              <div
                key={gene.geneId}
                className="border-b border-slate-50 last:border-b-0"
              >
                <div className="flex items-center gap-2 px-3 py-2">
                  <button
                    type="button"
                    onClick={() => toggleExpand(gene.geneId)}
                    className="shrink-0 rounded p-0.5 text-slate-400 hover:bg-slate-100"
                  >
                    {isExpanded ? (
                      <ChevronUp className="h-3 w-3" />
                    ) : (
                      <ChevronDown className="h-3 w-3" />
                    )}
                  </button>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-[11px] font-semibold text-slate-800">
                        {gene.geneId}
                      </span>
                      {gene.organism && (
                        <span className="truncate text-[10px] text-slate-400">
                          {gene.organism}
                        </span>
                      )}
                    </div>
                    {gene.displayName && gene.displayName !== gene.geneId && (
                      <div className="truncate text-[10px] text-slate-500">
                        {gene.displayName}
                      </div>
                    )}
                  </div>

                  {(() => {
                    const isPos = positiveGeneIds.has(gene.geneId);
                    const isNeg = negativeGeneIds.has(gene.geneId);
                    const assigned = isPos || isNeg;
                    return (
                      <div className="flex shrink-0 gap-1">
                        {isPos ? (
                          <span className="flex items-center gap-0.5 rounded border border-emerald-300 bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                            <Check className="h-2.5 w-2.5" />
                            Pos
                          </span>
                        ) : (
                          <button
                            type="button"
                            disabled={assigned}
                            onClick={() => onAddPositive(toResolvedGene(gene))}
                            title={
                              isNeg
                                ? "Already in Negative Controls"
                                : "Add to Positive Controls"
                            }
                            className="flex items-center gap-0.5 rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            <Plus className="h-2.5 w-2.5" />
                            Pos
                          </button>
                        )}
                        {isNeg ? (
                          <span className="flex items-center gap-0.5 rounded border border-red-300 bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-700">
                            <Check className="h-2.5 w-2.5" />
                            Neg
                          </span>
                        ) : (
                          <button
                            type="button"
                            disabled={assigned}
                            onClick={() => onAddNegative(toResolvedGene(gene))}
                            title={
                              isPos
                                ? "Already in Positive Controls"
                                : "Add to Negative Controls"
                            }
                            className="flex items-center gap-0.5 rounded border border-red-200 bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            <Minus className="h-2.5 w-2.5" />
                            Neg
                          </button>
                        )}
                      </div>
                    );
                  })()}
                </div>

                {isExpanded && (
                  <div className="space-y-0.5 bg-slate-50 px-3 py-2 pl-9 text-[10px] text-slate-600">
                    {gene.product && (
                      <div>
                        <span className="font-medium text-slate-500">Product: </span>
                        {gene.product}
                      </div>
                    )}
                    {gene.organism && (
                      <div>
                        <span className="font-medium text-slate-500">Organism: </span>
                        {gene.organism}
                      </div>
                    )}
                    {gene.matchedFields.length > 0 && (
                      <div>
                        <span className="font-medium text-slate-500">Matched in: </span>
                        {gene.matchedFields.join(", ")}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
      </div>

      {/* Footer – pagination */}
      {searched && totalCount > 0 && (
        <div className="flex items-center justify-between border-t border-slate-100 px-3 py-1.5">
          <span className="text-[10px] text-slate-400">
            {rangeStart}–{rangeEnd} of {totalCount}
          </span>
          {totalPages > 1 && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => goToPage(page - 1)}
                disabled={page === 0 || loading}
                className="flex items-center rounded border border-slate-200 bg-white p-0.5 text-slate-500 transition hover:bg-slate-50 disabled:opacity-30"
                aria-label="Previous page"
              >
                <ChevronLeft className="h-3 w-3" />
              </button>
              <span className="min-w-[3rem] text-center text-[10px] text-slate-500">
                {page + 1} / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => goToPage(page + 1)}
                disabled={page >= totalPages - 1 || loading}
                className="flex items-center rounded border border-slate-200 bg-white p-0.5 text-slate-500 transition hover:bg-slate-50 disabled:opacity-30"
                aria-label="Next page"
              >
                <ChevronRight className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
