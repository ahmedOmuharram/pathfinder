"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useDebouncedCallback } from "use-debounce";
import type { GeneSearchResult } from "@pathfinder/shared";
import { listOrganisms, searchGenes } from "@/lib/api/genes";
import { useSessionStore } from "@/state/useSessionStore";

const PAGE_SIZE = 30;

interface GeneSearchState {
  query: string;
  setQuery: (q: string) => void;
  results: GeneSearchResult[];
  totalCount: number;
  loading: boolean;
  loadingMore: boolean;
  error: string | null;
  setError: (err: string | null) => void;
  hasMore: boolean;
  loadMore: () => void;

  // Organism filter
  organisms: string[];
  selectedOrganism: string | null;
  setSelectedOrganism: (org: string | null) => void;
  organismFilter: string;
  setOrganismFilter: (f: string) => void;
  filteredOrganisms: string[];

  // Selection reset hook — called when search criteria change
  clearSelections: () => void;
}

export function useGeneSearch(onSelectionsCleared: () => void): GeneSearchState {
  const selectedSite = useSessionStore((s) => s.selectedSite);

  // Search state
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeneSearchResult[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Organism filter
  const [organisms, setOrganisms] = useState<string[]>([]);
  const [selectedOrganism, setSelectedOrganism] = useState<string | null>(null);
  const [organismFilter, setOrganismFilter] = useState("");

  const filteredOrganisms = useMemo(
    () =>
      organisms.filter((org) =>
        org.toLowerCase().includes(organismFilter.toLowerCase()),
      ),
    [organisms, organismFilter],
  );

  // Fetch all organisms on mount / site change
  useEffect(() => {
    let cancelled = false;
    listOrganisms(selectedSite)
      .then((orgs) => {
        if (!cancelled) setOrganisms(orgs);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedSite]);

  // Search implementation
  const currentQueryRef = useRef("");
  const resultsLengthRef = useRef(0);
  resultsLengthRef.current = results.length;

  const doSearch = useCallback(
    async (q: string, organism: string | null, append = false) => {
      if (!q.trim()) {
        if (!append) {
          setResults([]);
          setTotalCount(0);
        }
        return;
      }

      const offset = append ? resultsLengthRef.current : 0;
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setError(null);

      try {
        currentQueryRef.current = q;
        const resp = await searchGenes(selectedSite, q, organism, PAGE_SIZE, offset);
        if (currentQueryRef.current !== q) return;

        if (append) {
          setResults((prev) => [...prev, ...resp.results]);
        } else {
          setResults(resp.results);
        }
        setTotalCount(resp.totalCount);
      } catch (err) {
        if (currentQueryRef.current === q) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [selectedSite],
  );

  // Trigger search on query change (debounced)
  const debouncedSearch = useDebouncedCallback((q: string, organism: string | null) => {
    onSelectionsCleared();
    void doSearch(q, organism);
  }, 300);

  useEffect(() => {
    onSelectionsCleared();
    if (!query.trim()) {
      setResults([]);
      setTotalCount(0);
      return;
    }
    debouncedSearch(query, selectedOrganism);
  }, [query, selectedOrganism, selectedSite, debouncedSearch, onSelectionsCleared]);

  const loadMore = useCallback(() => {
    void doSearch(query, selectedOrganism, true);
  }, [doSearch, query, selectedOrganism]);

  return {
    query,
    setQuery,
    results,
    totalCount,
    loading,
    loadingMore,
    error,
    setError,
    hasMore: results.length < totalCount,
    loadMore,
    organisms,
    selectedOrganism,
    setSelectedOrganism,
    organismFilter,
    setOrganismFilter,
    filteredOrganisms,
    clearSelections: onSelectionsCleared,
  };
}
