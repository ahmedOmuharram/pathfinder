"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Search } from "lucide-react";
import type { GeneSearchResult } from "@pathfinder/shared";
import { searchGenes } from "@/lib/api/genes";
import { Input } from "@/lib/components/ui/Input";

interface GeneAutocompleteProps {
  siteId: string;
  onSelect: (geneId: string) => void;
  placeholder?: string;
  excludeIds?: Set<string>;
}

export function GeneAutocomplete({
  siteId,
  onSelect,
  placeholder = "Search genes...",
  excludeIds,
}: GeneAutocompleteProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeneSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced search
  useEffect(() => {
    if (!query.trim() || !siteId) {
      setResults([]);
      setOpen(false);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void (async () => {
        setLoading(true);
        try {
          const resp = await searchGenes(siteId, query.trim(), null, 10);
          const filtered = excludeIds
            ? resp.results.filter((r) => !excludeIds.has(r.geneId))
            : resp.results;
          setResults(filtered);
          setOpen(filtered.length > 0);
        } finally {
          setLoading(false);
        }
      })();
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, siteId, excludeIds]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleSelect = useCallback(
    (geneId: string) => {
      onSelect(geneId);
      setQuery("");
      setOpen(false);
      setResults([]);
    },
    [onSelect],
  );

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
    }
  }, []);

  return (
    <div ref={dropdownRef} className="relative">
      <div className="relative">
        <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="h-7 bg-background pl-7 pr-7 text-xs"
        />
        {loading && (
          <Loader2 className="absolute right-2 top-1/2 h-3 w-3 -translate-y-1/2 animate-spin text-muted-foreground" />
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-48 overflow-y-auto rounded-md border border-border bg-popover shadow-lg animate-hover-card-in">
          {results.map((gene) => (
            <button
              key={gene.geneId}
              type="button"
              onClick={() => handleSelect(gene.geneId)}
              className="flex w-full items-start gap-2 px-3 py-2 text-left transition-colors duration-75 hover:bg-accent"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-mono text-xs font-medium text-foreground">
                  {gene.geneId}
                </p>
                <p className="truncate text-[10px] text-muted-foreground">
                  {gene.product || "\u2014"}
                </p>
                <p className="truncate text-[10px] italic text-muted-foreground/70">
                  {gene.organism}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
