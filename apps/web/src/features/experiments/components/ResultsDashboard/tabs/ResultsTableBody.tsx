import { useCallback } from "react";
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  ArrowUpDown,
  X,
  Loader2,
} from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import type { WdkSortDir } from "@/features/experiments/constants";
import type { RecordAttribute, WdkRecord } from "../../../api";
import {
  getPrimaryKey,
  ClassificationBadge,
  AttributeValue,
  AttributeValueRich,
  PAGE_SIZE_OPTIONS,
} from "./ResultsTableColumns";

/* ------------------------------------------------------------------ */
/*  Public types                                                       */
/* ------------------------------------------------------------------ */

export interface ResultsTableBodyProps {
  records: WdkRecord[];
  orderedColumns: RecordAttribute[];
  hasClassification: boolean;
  loading: boolean;

  sortColumn: string | null;
  sortDir: WdkSortDir;
  onSort: (colName: string) => void;

  expandedKey: string | null;
  detail: Record<string, unknown> | null;
  detailLoading: boolean;
  onExpandRow: (key: string, recordId: WdkRecord["id"]) => void;
}

export interface PaginationProps {
  offset: number;
  pageSize: number;
  totalCount: number;
  loading: boolean;
  onOffsetChange: (offset: number) => void;
  onPageSizeChange: (size: number) => void;
}

/* ------------------------------------------------------------------ */
/*  ResultsTableBody                                                   */
/* ------------------------------------------------------------------ */

export function ResultsTableBody({
  records,
  orderedColumns,
  hasClassification,
  loading,
  sortColumn,
  sortDir,
  onSort,
  expandedKey,
  detail,
  detailLoading,
  onExpandRow,
}: ResultsTableBodyProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50">
            {hasClassification && (
              <th className="whitespace-nowrap px-4 py-2.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Class
              </th>
            )}
            {orderedColumns.map((col) => (
              <th key={col.name} className="whitespace-nowrap px-4 py-2.5">
                <button
                  type="button"
                  onClick={() => onSort(col.name)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
                >
                  {col.displayName}
                  {sortColumn === col.name ? (
                    sortDir === "ASC" ? (
                      <ChevronUp className="h-3 w-3" />
                    ) : (
                      <ChevronDown className="h-3 w-3" />
                    )
                  ) : (
                    <ArrowUpDown className="h-3 w-3 opacity-40" />
                  )}
                </button>
              </th>
            ))}
            <th className="w-8 px-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {loading && records.length === 0 ? (
            <tr>
              <td
                colSpan={orderedColumns.length + (hasClassification ? 1 : 0) + 1}
                className="py-16 text-center"
              >
                <Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" />
              </td>
            </tr>
          ) : records.length === 0 ? (
            <tr>
              <td
                colSpan={orderedColumns.length + (hasClassification ? 1 : 0) + 1}
                className="py-16 text-center text-sm text-muted-foreground"
              >
                No records found.
              </td>
            </tr>
          ) : (
            records.map((record) => {
              const pk = getPrimaryKey(record);
              const isExpanded = expandedKey === pk;
              return (
                <RecordRow
                  key={pk}
                  record={record}
                  pk={pk}
                  columns={orderedColumns}
                  hasClassification={hasClassification}
                  isExpanded={isExpanded}
                  detail={isExpanded ? detail : null}
                  detailLoading={isExpanded && detailLoading}
                  onToggle={() => onExpandRow(pk, record.id)}
                />
              );
            })
          )}
        </tbody>
      </table>

      {loading && records.length > 0 && (
        <div className="flex items-center justify-center border-t border-border bg-muted/30 py-2">
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Pagination                                                         */
/* ------------------------------------------------------------------ */

export function Pagination({
  offset,
  pageSize,
  totalCount,
  loading,
  onOffsetChange,
  onPageSizeChange,
}: PaginationProps) {
  const currentPage = Math.floor(offset / pageSize) + 1;
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const hasPrev = offset > 0;
  const hasNext = offset + pageSize < totalCount;

  const handlePageSizeChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      onPageSizeChange(Number(e.target.value));
      onOffsetChange(0);
    },
    [onPageSizeChange, onOffsetChange],
  );

  return (
    <div className="flex items-center justify-between text-xs text-muted-foreground">
      <div className="flex items-center gap-2">
        <span>Rows per page</span>
        <select
          value={pageSize}
          onChange={handlePageSizeChange}
          className="rounded-md border border-border bg-background px-2 py-1 text-xs"
        >
          {PAGE_SIZE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-3">
        <span className="tabular-nums">
          Page {currentPage} of {totalPages}
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7"
            disabled={!hasPrev || loading}
            onClick={() => onOffsetChange(Math.max(0, offset - pageSize))}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="h-7 w-7"
            disabled={!hasNext || loading}
            onClick={() => onOffsetChange(offset + pageSize)}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  RecordRow                                                          */
/* ------------------------------------------------------------------ */

function RecordRow({
  record,
  pk,
  columns,
  hasClassification,
  isExpanded,
  detail,
  detailLoading,
  onToggle,
}: {
  record: WdkRecord;
  pk: string;
  columns: RecordAttribute[];
  hasClassification: boolean;
  isExpanded: boolean;
  detail: Record<string, unknown> | null;
  detailLoading: boolean;
  onToggle: () => void;
}) {
  const colSpan = columns.length + (hasClassification ? 1 : 0) + 1;

  return (
    <>
      <tr
        onClick={onToggle}
        className="cursor-pointer transition-colors hover:bg-accent/50 data-[expanded=true]:bg-accent/30"
        data-expanded={isExpanded}
      >
        {hasClassification && (
          <td className="px-4 py-2">
            <ClassificationBadge value={record._classification ?? null} />
          </td>
        )}
        {columns.map((col) => (
          <td
            key={col.name}
            className="max-w-[300px] truncate px-4 py-2 text-sm text-foreground"
          >
            <AttributeValue value={record.attributes[col.name]} />
          </td>
        ))}
        <td className="px-2 py-2 text-muted-foreground">
          {isExpanded ? (
            <ChevronUp className="h-3.5 w-3.5" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5" />
          )}
        </td>
      </tr>
      <tr>
        <td colSpan={colSpan} className="p-0">
          <div
            className="overflow-hidden transition-all duration-200 ease-in-out"
            style={{
              maxHeight: isExpanded ? "500px" : "0px",
              opacity: isExpanded ? 1 : 0,
            }}
          >
            <DetailPanel
              pk={pk}
              detail={detail}
              loading={detailLoading}
              onClose={onToggle}
            />
          </div>
        </td>
      </tr>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  DetailPanel                                                        */
/* ------------------------------------------------------------------ */

function DetailPanel({
  pk,
  detail,
  loading,
  onClose,
}: {
  pk: string;
  detail: Record<string, unknown> | null;
  loading: boolean;
  onClose: () => void;
}) {
  const attrs =
    detail && typeof detail.attributes === "object" && detail.attributes != null
      ? (detail.attributes as Record<string, unknown>)
      : detail;

  return (
    <div className="border-t border-border bg-muted/30 px-6 py-4">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Record Detail — {pk}
        </h4>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onClose();
          }}
          className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading details…
        </div>
      ) : attrs ? (
        <div className="max-h-72 overflow-y-auto">
          <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-sm">
            {Object.entries(attrs).map(([key, val]) => (
              <div key={key} className="contents">
                <dt className="whitespace-nowrap font-medium text-muted-foreground">
                  {key}
                </dt>
                <dd className="text-foreground">
                  <AttributeValueRich value={val} />
                </dd>
              </div>
            ))}
          </dl>
        </div>
      ) : (
        <p className="py-4 text-sm text-muted-foreground">Unable to load details.</p>
      )}
    </div>
  );
}
