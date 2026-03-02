import { useRef, useEffect } from "react";
import { Columns } from "lucide-react";
import { Button } from "@/lib/components/ui/Button";
import type { RecordAttribute } from "../../../api";

interface ResultsTableHeaderProps {
  totalCount: number;
  attributes: RecordAttribute[];
  visibleColumns: Set<string>;
  columnsOpen: boolean;
  onColumnsOpenChange: (open: boolean) => void;
  onToggleColumn: (name: string) => void;
}

export function ResultsTableHeader({
  totalCount,
  attributes,
  visibleColumns,
  columnsOpen,
  onColumnsOpenChange,
  onToggleColumn,
}: ResultsTableHeaderProps) {
  const columnsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (columnsRef.current && !columnsRef.current.contains(e.target as Node)) {
        onColumnsOpenChange(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onColumnsOpenChange]);

  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-xs text-muted-foreground tabular-nums">
        {totalCount.toLocaleString()} records
      </p>

      <div className="flex items-center gap-2">
        <div ref={columnsRef} className="relative">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onColumnsOpenChange(!columnsOpen)}
          >
            <Columns className="h-3.5 w-3.5" />
            Columns
          </Button>

          {columnsOpen && (
            <div className="absolute right-0 top-full z-30 mt-1 w-64 rounded-lg border border-border bg-popover p-2 shadow-lg">
              <div className="max-h-60 overflow-y-auto space-y-0.5">
                {attributes.map((attr) => (
                  <label
                    key={attr.name}
                    className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={visibleColumns.has(attr.name)}
                      onChange={() => onToggleColumn(attr.name)}
                      className="rounded border-border"
                    />
                    <span className="truncate">{attr.displayName}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
