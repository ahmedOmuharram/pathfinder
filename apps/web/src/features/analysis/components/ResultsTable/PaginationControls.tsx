import { useCallback } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import { PAGE_SIZE_OPTIONS } from "./ResultsTableColumns";

interface PaginationControlsProps {
  offset: number;
  pageSize: number;
  totalCount: number;
  loading: boolean;
  onOffsetChange: (offset: number) => void;
  onPageSizeChange: (size: number) => void;
}

export function PaginationControls({
  offset,
  pageSize,
  totalCount,
  loading,
  onOffsetChange,
  onPageSizeChange,
}: PaginationControlsProps) {
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
