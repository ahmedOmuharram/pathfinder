import { useState, useCallback } from "react";
import { useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import type { WdkRecord, RecordsResponse } from "@/lib/types/wdk";
import type { WdkSortDir } from "@/features/analysis/constants";
import { getRecords, type EntityRef } from "@/features/analysis/api/stepResults";

interface ResultsTableRecordsState {
  records: WdkRecord[];
  meta: RecordsResponse["meta"] | null;
  loading: boolean;
  error: string | null;
  offset: number;
  pageSize: number;
  sortColumn: string | null;
  sortDir: WdkSortDir;
  setOffset: (offset: number) => void;
  setPageSize: (size: number) => void;
  handleSort: (colName: string) => void;
  resetSort: () => void;
  refetch: () => void;
}

export function useResultsTableRecords(
  entityRef: EntityRef,
  visibleColumns: Set<string>,
): ResultsTableRecordsState {
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<WdkSortDir>("ASC");

  const queryClient = useQueryClient();

  const attributes = [...visibleColumns];

  const { data, isLoading, error } = useQuery({
    queryKey: ["experiments", "records", entityRef.type, entityRef.id, {
      offset,
      pageSize,
      sortColumn,
      sortDir,
      attributes,
    }] as const,
    queryFn: () =>
      getRecords(entityRef, {
        offset,
        limit: pageSize,
        ...(sortColumn != null ? { sort: sortColumn, dir: sortDir } : {}),
        attributes,
      }),
    enabled: visibleColumns.size > 0,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });

  const handleSort = useCallback(
    (colName: string) => {
      if (sortColumn === colName) {
        setSortDir((d) => (d === "ASC" ? "DESC" : "ASC"));
      } else {
        setSortColumn(colName);
        setSortDir("ASC");
      }
      setOffset(0);
    },
    [sortColumn],
  );

  const resetSort = useCallback(() => {
    setSortColumn(null);
    setSortDir("ASC");
  }, []);

  const invalidateAndRefetch = useCallback(() => {
    void queryClient.invalidateQueries({
      queryKey: ["experiments", "records", entityRef.type, entityRef.id],
    });
  }, [queryClient, entityRef.type, entityRef.id]);

  return {
    records: data?.records ?? [],
    meta: data?.meta ?? null,
    loading: isLoading,
    error: error != null ? (error instanceof Error ? error.message : String(error)) : null,
    offset,
    pageSize,
    sortColumn,
    sortDir,
    setOffset,
    setPageSize,
    handleSort,
    resetSort,
    refetch: invalidateAndRefetch,
  };
}
