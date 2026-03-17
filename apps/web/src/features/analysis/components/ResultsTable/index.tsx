import { useState, useEffect, useCallback, useRef } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import type { WdkSortDir } from "@/features/analysis/constants";
import type { WdkRecord, RecordDetail } from "@/lib/types/wdk";
import {
  getAttributes,
  getRecords,
  getRecordDetail,
  type EntityRef,
  type RecordAttribute,
  type RecordsResponse,
} from "@/features/analysis/api/stepResults";
import { ResultsTableHeader } from "./ResultsTableHeader";
import { ResultsTableBody } from "./ResultsTableBody";
import { PaginationControls } from "./PaginationControls";

interface ResultsTableProps {
  entityRef: EntityRef;
}

export function ResultsTable({ entityRef }: ResultsTableProps) {
  /* ---------- attribute / column state ---------- */
  const [attributes, setAttributes] = useState<RecordAttribute[]>([]);
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(new Set());
  const [columnsOpen, setColumnsOpen] = useState(false);

  /* ---------- records / pagination state ---------- */
  const [records, setRecords] = useState<WdkRecord[]>([]);
  const [meta, setMeta] = useState<RecordsResponse["meta"] | null>(null);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<WdkSortDir>("ASC");

  /* ---------- loading / error ---------- */
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* ---------- abort controller for record fetches ---------- */
  const abortRef = useRef<AbortController | null>(null);

  /* ---------- row expansion state ---------- */
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [detail, setDetail] = useState<RecordDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  /* ---------- fetch attributes on entity change ---------- */
  useEffect(() => {
    let cancelled = false;
    setVisibleColumns(new Set());
    setSortColumn(null);
    setSortDir("ASC");
    const fetchAttrs = getAttributes(entityRef);
    fetchAttrs
      .then(({ attributes: attrs }) => {
        if (cancelled) return;
        const displayable = attrs.filter((a) => a.isDisplayable !== false);
        if (displayable.length === 0) {
          setAttributes([]);
          setLoading(false);
          return;
        }
        setAttributes(displayable);
        setVisibleColumns(new Set(displayable.slice(0, 6).map((a) => a.name)));
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [entityRef]);

  /* ---------- fetch records ---------- */
  const fetchRecords = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const opts = {
        offset,
        limit: pageSize,
        sort: sortColumn ?? undefined,
        dir: sortColumn ? sortDir : undefined,
        attributes: [...visibleColumns],
      };
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
    if (visibleColumns.size > 0) fetchRecords();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchRecords already depends on visibleColumns
  }, [fetchRecords]);

  /* ---------- handlers ---------- */
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

  const handleExpandRow = useCallback(
    async (key: string, recordId: WdkRecord["id"]) => {
      if (expandedKey === key) {
        setExpandedKey(null);
        setDetail(null);
        setDetailError(null);
        return;
      }
      setExpandedKey(key);
      setDetail(null);
      setDetailError(null);
      setDetailLoading(true);
      try {
        const d = await getRecordDetail(entityRef, recordId);
        setDetail(d);
      } catch (err) {
        setDetail(null);
        setDetailError(
          err instanceof Error ? err.message : "Failed to load record details",
        );
      } finally {
        setDetailLoading(false);
      }
    },
    [entityRef, expandedKey],
  );

  const toggleColumn = useCallback((name: string) => {
    setVisibleColumns((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
    setOffset(0);
  }, []);

  /* ---------- derived values ---------- */
  const totalCount = meta?.totalCount ?? 0;
  const orderedColumns = attributes.filter((a) => visibleColumns.has(a.name));
  const hasClassification = records.some((r) => r._classification != null);

  /* ---------- error state ---------- */
  if (error && records.length === 0) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" className="mt-3" onClick={fetchRecords}>
          Retry
        </Button>
      </div>
    );
  }

  /* ---------- render ---------- */
  return (
    <div className="space-y-3">
      <ResultsTableHeader
        totalCount={totalCount}
        attributes={attributes}
        visibleColumns={visibleColumns}
        columnsOpen={columnsOpen}
        onColumnsOpenChange={setColumnsOpen}
        onToggleColumn={toggleColumn}
      />

      <ResultsTableBody
        records={records}
        orderedColumns={orderedColumns}
        hasClassification={hasClassification}
        loading={loading}
        sortColumn={sortColumn}
        sortDir={sortDir}
        onSort={handleSort}
        expandedKey={expandedKey}
        detail={detail}
        detailError={detailError}
        detailLoading={detailLoading}
        onExpandRow={handleExpandRow}
      />

      <PaginationControls
        offset={offset}
        pageSize={pageSize}
        totalCount={totalCount}
        loading={loading}
        onOffsetChange={setOffset}
        onPageSizeChange={setPageSize}
      />
    </div>
  );
}
