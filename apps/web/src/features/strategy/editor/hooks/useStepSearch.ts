"use client";

import { useEffect, useMemo, useState, startTransition } from "react";
import type { Search } from "@pathfinder/shared";
import { getSearches } from "@/lib/api/sites";
import { normalizeRecordType } from "@/lib/utils/normalizeRecordType";

interface UseStepSearchArgs {
  siteId: string;
  /** The strategy-level record type. */
  recordType: string | null;
  /** Initial search name from the step. */
  initialSearchName: string;
  /** Resolves record type for search fetching. */
  resolveRecordTypeForSearch: (searchRecordType?: string | null) => string;
}

export function useStepSearch({
  siteId,
  recordType,
  initialSearchName,
  resolveRecordTypeForSearch,
}: UseStepSearchArgs) {
  const [editableSearchName, setEditableSearchName] = useState(initialSearchName);
  const [searchOptions, setSearchOptions] = useState<Search[]>([]);
  const [isLoadingSearches, setIsLoadingSearches] = useState(false);
  const [searchListError, setSearchListError] = useState<string | null>(null);

  const searchName = editableSearchName.trim();

  const selectedSearch = useMemo(() => {
    if (!searchName) return null;
    return searchOptions.find((option) => option.name === searchName) || null;
  }, [searchName, searchOptions]);

  const isSearchNameAvailable = useMemo(
    () =>
      searchName ? searchOptions.some((option) => option.name === searchName) : true,
    [searchName, searchOptions],
  );

  const filteredSearchOptions = useMemo(() => {
    const query = editableSearchName.trim().toLowerCase();
    if (!query) return searchOptions;
    return searchOptions.filter((option) => {
      const label = (option.displayName || option.name).toLowerCase();
      return label.includes(query) || option.name.toLowerCase().includes(query);
    });
  }, [editableSearchName, searchOptions]);

  // -------------------------------------------------------------------------
  // Data fetching: searches
  // -------------------------------------------------------------------------
  useEffect(() => {
    let isActive = true;
    const resolvedRecordType = resolveRecordTypeForSearch();
    const normalizedRecordType = normalizeRecordType(resolvedRecordType || recordType);
    if (!normalizedRecordType) {
      startTransition(() => {
        setSearchOptions([]);
        setSearchListError(null);
      });
      return;
    }
    startTransition(() => {
      setIsLoadingSearches(true);
      setSearchListError(null);
    });
    getSearches(siteId, normalizedRecordType)
      .then((results) => {
        if (!isActive) return;
        const options = (results || [])
          .filter((item): item is Search => Boolean(item && item.name))
          .sort((a, b) =>
            (a.displayName || a.name).localeCompare(b.displayName || b.name),
          );
        setSearchOptions(options);
        if (options.length === 0) {
          setSearchListError("No searches available for this record type.");
        }
      })
      .catch((err) => {
        console.error("[StepEditor.loadSearches]", err);
        if (!isActive) return;
        setSearchOptions([]);
        setSearchListError("Failed to load search list.");
      })
      .finally(() => {
        if (!isActive) return;
        setIsLoadingSearches(false);
      });
    return () => {
      isActive = false;
    };
  }, [siteId, recordType, resolveRecordTypeForSearch]);

  return {
    editableSearchName,
    setEditableSearchName,
    searchName,
    selectedSearch,
    isSearchNameAvailable,
    searchOptions,
    filteredSearchOptions,
    isLoadingSearches,
    searchListError,
  };
}
