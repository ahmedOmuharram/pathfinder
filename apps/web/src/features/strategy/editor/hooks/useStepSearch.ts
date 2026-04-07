"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Search } from "@pathfinder/shared";
import { searchesOptions } from "@/lib/api/sites";
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

  const searchName = editableSearchName.trim();

  const resolvedRecordType = resolveRecordTypeForSearch();
  const normalizedRecordType = normalizeRecordType(resolvedRecordType || recordType);

  const {
    data: rawSearches = [],
    isLoading: isLoadingSearches,
    error: searchQueryError,
  } = useQuery(searchesOptions(siteId, normalizedRecordType));

  const searchOptions: Search[] = useMemo(
    () =>
      [...rawSearches].sort((a, b) =>
        (a.displayName || a.name).localeCompare(b.displayName || b.name),
      ),
    [rawSearches],
  );

  const searchListError = useMemo(() => {
    if (searchQueryError != null) return "Failed to load search list.";
    if (!isLoadingSearches && searchOptions.length === 0 && normalizedRecordType != null && normalizedRecordType !== "")
      return "No searches available for this record type.";
    return null;
  }, [searchQueryError, isLoadingSearches, searchOptions.length, normalizedRecordType]);

  const selectedSearch = useMemo(() => {
    if (searchName === "") return null;
    return searchOptions.find((option) => option.name === searchName) ?? null;
  }, [searchName, searchOptions]);

  const isSearchNameAvailable = useMemo(
    () =>
      searchName !== ""
        ? searchOptions.some((option) => option.name === searchName)
        : true,
    [searchName, searchOptions],
  );

  const filteredSearchOptions = useMemo(() => {
    const query = editableSearchName.trim().toLowerCase();
    if (query === "") return searchOptions;
    return searchOptions.filter((option) => {
      const label = (option.displayName || option.name).toLowerCase();
      return label.includes(query) || option.name.toLowerCase().includes(query);
    });
  }, [editableSearchName, searchOptions]);

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
