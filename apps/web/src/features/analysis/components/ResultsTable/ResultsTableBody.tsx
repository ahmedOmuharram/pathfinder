import { ChevronDown, ChevronUp, ArrowUpDown, Loader2 } from "lucide-react";
import type { WdkSortDir } from "@/features/analysis/constants";
import type { RecordAttribute, RecordDetail, WdkRecord } from "@/lib/types/wdk";
import { getPrimaryKey } from "./ResultsTableColumns";
import { RecordRow } from "./RecordRow";

/* ------------------------------------------------------------------ */
/*  Public types                                                       */
/* ------------------------------------------------------------------ */

interface ResultsTableBodyProps {
  records: WdkRecord[];
  orderedColumns: RecordAttribute[];
  hasClassification: boolean;
  loading: boolean;

  sortColumn: string | null;
  sortDir: WdkSortDir;
  onSort: (colName: string) => void;

  expandedKey: string | null;
  detail: RecordDetail | null;
  detailError: string | null;
  detailLoading: boolean;
  onExpandRow: (key: string, recordId: WdkRecord["id"]) => void;
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
  detailError,
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
                {col.isSortable !== false ? (
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
                ) : (
                  <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {col.displayName}
                  </span>
                )}
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
                  detailError={isExpanded ? detailError : null}
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
