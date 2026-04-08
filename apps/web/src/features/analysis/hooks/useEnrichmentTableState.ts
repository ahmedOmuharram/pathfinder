import { useState } from "react";
import type { EnrichmentTerm } from "@pathfinder/shared";
import type { SortDir } from "../constants";
import type { SortKey } from "../components/enrichment-utils";

interface EnrichmentTableState {
  sorted: EnrichmentTerm[];
  sortKey: SortKey;
  sortDir: SortDir;
  expandedIds: Set<string>;
  toggleSort: (key: SortKey) => void;
  toggleExpand: (termId: string) => void;
}

export function useEnrichmentTableState(terms: EnrichmentTerm[]): EnrichmentTableState {
  const [sortKey, setSortKey] = useState<SortKey>("pValue");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const sorted = (() => {
    const copy = [...terms];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "number" && typeof bv === "number") {
        return sortDir === "asc" ? av - bv : bv - av;
      }
      return sortDir === "asc"
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
    return copy;
  })();

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(
        key === "termName" || key === "pValue" || key === "fdr" ? "asc" : "desc",
      );
    }
  };

  const toggleExpand = (termId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(termId)) {
        next.delete(termId);
      } else {
        next.add(termId);
      }
      return next;
    });
  };

  return { sorted, sortKey, sortDir, expandedIds, toggleSort, toggleExpand };
}
