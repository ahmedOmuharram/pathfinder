import { useState, useEffect, useCallback, useRef } from "react";
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
  setError: (error: string | null) => void;
  setLoading: (loading: boolean) => void;
  handleSort: (colName: string) => void;
  resetSort: () => void;
  fetchRecords: () => Promise<void>;
}

export function useResultsTableRecords(
  entityRef: EntityRef,
  visibleColumns: Set<string>,
): ResultsTableRecordsState {
  const [records, setRecords] = useState<WdkRecord[]>([]);
  const [meta, setMeta] = useState<RecordsResponse["meta"] | null>(null);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<WdkSortDir>("ASC");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const fetchRecords = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const opts: Parameters<typeof getRecords>[1] = {
        offset,
        limit: pageSize,
        attributes: [...visibleColumns],
      };
      if (sortColumn != null) {
        opts.sort = sortColumn;
        opts.dir = sortDir;
      }
      const res = await getRecords(entityRef, opts);
      if (controller.signal.aborted) return;
      setRecords(res.records);
      setMeta(res.meta);
    } catch (err) {
      if (controller.signal.aborted) return;
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [entityRef, offset, pageSize, sortColumn, sortDir, visibleColumns]);

  useEffect(() => {
    if (visibleColumns.size > 0) void fetchRecords();
  }, [fetchRecords, visibleColumns.size]);

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

  return {
    records,
    meta,
    loading,
    error,
    offset,
    pageSize,
    sortColumn,
    sortDir,
    setOffset,
    setPageSize,
    setError,
    setLoading,
    handleSort,
    resetSort,
    fetchRecords,
  };
}
