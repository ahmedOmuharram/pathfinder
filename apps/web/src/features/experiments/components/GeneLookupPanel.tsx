import { useCallback, useEffect, useRef, useState } from "react";
import type { GeneSearchResult, ResolvedGene } from "@pathfinder/shared";
import { searchGenes } from "@/lib/api/client";
import { Search, X } from "lucide-react";
import { GeneLookupSearch } from "./GeneLookupSearch";
import { GeneLookupResults } from "./GeneLookupResults";

const PAGE_SIZE = 50;

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

  const toggleExpand = useCallback((geneId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(geneId)) next.delete(geneId);
      else next.add(geneId);
      return next;
    });
  }, []);

  return (
    <div className="rounded-lg border border-primary/20 bg-card shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-primary/10 px-3 py-2">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-primary">
          <Search className="h-3.5 w-3.5" />
          Find Gene IDs
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-0.5 text-muted-foreground transition hover:bg-muted hover:text-muted-foreground"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <GeneLookupSearch
        query={query}
        organism={organism}
        onQueryChange={setQuery}
        onOrganismChange={setOrganism}
      />

      <GeneLookupResults
        results={results}
        totalCount={totalCount}
        page={page}
        loading={loading}
        searched={searched}
        query={query}
        organism={organism}
        suggestedOrganisms={suggestedOrganisms}
        expanded={expanded}
        positiveGeneIds={positiveGeneIds}
        negativeGeneIds={negativeGeneIds}
        resultsRef={resultsRef}
        onSetQuery={setQuery}
        onSetOrganism={setOrganism}
        onGoToPage={goToPage}
        onToggleExpand={toggleExpand}
        onAddPositive={onAddPositive}
        onAddNegative={onAddNegative}
      />
    </div>
  );
}
