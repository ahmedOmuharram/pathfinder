"use client";

import { useCallback, useState } from "react";
import type { GeneSearchResult } from "@pathfinder/shared";

interface GeneSelectionState {
  selectedIds: Set<string>;
  hasSelection: boolean;
  toggleSelect: (geneId: string) => void;
  toggleSelectAll: (results: GeneSearchResult[]) => void;
  clearSelection: () => void;
  selectedArray: () => string[];
}

export function useGeneSelection(): GeneSelectionState {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const toggleSelect = useCallback((geneId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(geneId)) next.delete(geneId);
      else next.add(geneId);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback((results: GeneSearchResult[]) => {
    setSelectedIds((prev) => {
      if (prev.size === results.length) return new Set();
      return new Set(results.map((r) => r.geneId));
    });
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const selectedArray = useCallback(() => [...selectedIds], [selectedIds]);

  return {
    selectedIds,
    hasSelection: selectedIds.size > 0,
    toggleSelect,
    toggleSelectAll,
    clearSelection,
    selectedArray,
  };
}
