"use client";

import { useState, useMemo } from "react";

interface ResultsTableProps {
  records: Record<string, unknown>[];
  columns: string[];
  totalCount: number;
}

export function ResultsTable({ records, columns, totalCount }: ResultsTableProps) {
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const sortedRecords = useMemo(() => {
    if (!sortColumn) return records;

    return [...records].sort((a, b) => {
      const aVal = String(a[sortColumn] || "");
      const bVal = String(b[sortColumn] || "");
      const comparison = aVal.localeCompare(bVal);
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [records, sortColumn, sortDirection]);

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortColumn(column);
      setSortDirection("asc");
    }
  };

  if (records.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-slate-500">
        No results to display
      </div>
    );
  }

  return (
    <div className="overflow-auto">
      <div className="mb-2 text-[11px] text-slate-500">
        Showing {records.length} of {totalCount.toLocaleString()} results
      </div>
      <table className="w-full text-[13px]">
        <thead>
          <tr className="border-b border-slate-200">
            {columns.map((col) => (
              <th
                key={col}
                onClick={() => handleSort(col)}
                className="cursor-pointer px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500 transition-colors hover:text-slate-900"
              >
                <div className="flex items-center gap-1">
                  {col}
                  {sortColumn === col && (
                    <svg
                      className={`h-4 w-4 transition-transform ${
                        sortDirection === "desc" ? "rotate-180" : ""
                      }`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 15l7-7 7 7"
                      />
                    </svg>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedRecords.map((record, i) => (
            <tr
              key={i}
              className="border-b border-slate-100 transition-colors hover:bg-slate-50"
            >
              {columns.map((col) => (
                <td key={col} className="px-3 py-2 text-slate-700">
                  {String(record[col] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
