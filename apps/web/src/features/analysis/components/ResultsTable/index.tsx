import { useState, useEffect, useCallback } from "react";
import { Button } from "@/lib/components/ui/Button";
import { getAttributes, type EntityRef } from "@/features/analysis/api/stepResults";
import { useResultsTableRecords } from "@/features/analysis/hooks/useResultsTableRecords";
import { useResultsTableDetail } from "@/features/analysis/hooks/useResultsTableDetail";
import type { RecordAttribute } from "@/lib/types/wdk";
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
  const [attrError, setAttrError] = useState<string | null>(null);

  /* ---------- records / pagination ---------- */
  const recordsState = useResultsTableRecords(entityRef, visibleColumns);
  const { resetSort, setOffset } = recordsState;

  /* ---------- row expansion ---------- */
  const detailState = useResultsTableDetail(entityRef);

  /* ---------- fetch attributes on entity change ---------- */
  useEffect(() => {
    let cancelled = false;
    getAttributes(entityRef)
      .then(({ attributes: attrs }) => {
        if (cancelled) return;
        setAttrError(null);
        resetSort();
        const displayable = attrs.filter((a) => a.isDisplayable !== false);
        setAttributes(displayable);
        if (displayable.length === 0) {
          setVisibleColumns(new Set());
          return;
        }
        setVisibleColumns(new Set(displayable.slice(0, 6).map((a) => a.name)));
      })
      .catch((err) => {
        if (!cancelled) setAttrError(String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [entityRef, resetSort]);

  /* ---------- handlers ---------- */
  const toggleColumn = useCallback(
    (name: string) => {
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
    },
    [setOffset],
  );

  /* ---------- derived values ---------- */
  const totalCount = recordsState.meta?.totalCount ?? 0;
  const orderedColumns = attributes.filter((a) => visibleColumns.has(a.name));
  const hasClassification = recordsState.records.some((r) => r._classification != null);

  /* ---------- error state ---------- */
  const displayError = attrError ?? recordsState.error;
  if (displayError != null && recordsState.records.length === 0) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
        <p className="text-sm text-destructive">{displayError}</p>
        <Button
          variant="outline"
          size="sm"
          className="mt-3"
          onClick={() => {
            recordsState.refetch();
          }}
        >
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
        records={recordsState.records}
        orderedColumns={orderedColumns}
        hasClassification={hasClassification}
        loading={recordsState.loading}
        sortColumn={recordsState.sortColumn}
        sortDir={recordsState.sortDir}
        onSort={recordsState.handleSort}
        expandedKey={detailState.expandedKey}
        detail={detailState.detail}
        detailError={detailState.detailError}
        detailLoading={detailState.detailLoading}
        onExpandRow={detailState.handleExpandRow}
      />

      <PaginationControls
        offset={recordsState.offset}
        pageSize={recordsState.pageSize}
        totalCount={totalCount}
        loading={recordsState.loading}
        onOffsetChange={recordsState.setOffset}
        onPageSizeChange={recordsState.setPageSize}
      />
    </div>
  );
}
