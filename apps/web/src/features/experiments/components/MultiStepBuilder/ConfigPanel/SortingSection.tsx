import type { RecordAttribute } from "../../../api/crud";
import { ArrowUpDown } from "lucide-react";

export interface SortingSectionProps {
  sortAttribute: string | null;
  onSortAttributeChange: (v: string | null) => void;
  sortDirection: "ASC" | "DESC";
  onSortDirectionChange: (v: "ASC" | "DESC") => void;
  sortableAttributes: RecordAttribute[];
}

export function SortingSection({
  sortAttribute,
  onSortAttributeChange,
  sortDirection,
  onSortDirectionChange,
  sortableAttributes,
}: SortingSectionProps) {
  return (
    <div className="space-y-2">
      <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <input
          type="checkbox"
          checked={sortAttribute !== null}
          onChange={(e) => {
            if (e.target.checked) {
              const suggested = sortableAttributes.find((a) => a.isSuggested);
              onSortAttributeChange(
                suggested?.name ?? sortableAttributes[0]?.name ?? null,
              );
            } else {
              onSortAttributeChange(null);
            }
          }}
          className="rounded border-input"
        />
        <ArrowUpDown className="h-3 w-3" />
        Enable result ranking
      </label>
      <p className="pl-5 text-[10px] text-muted-foreground">
        Rank results by a numeric attribute to compute Top-K metrics (P@K, R@K, E@K).
      </p>
      {sortAttribute !== null && (
        <div className="space-y-2 rounded-md border border-border bg-muted/30 p-3">
          <div>
            <label className="mb-1 block text-[10px] font-medium text-muted-foreground">
              Sort attribute
            </label>
            <select
              className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-xs"
              value={sortAttribute}
              onChange={(e) => onSortAttributeChange(e.target.value)}
            >
              {sortableAttributes.length === 0 && (
                <option value="">No sortable attributes found</option>
              )}
              {sortableAttributes.map((a) => (
                <option key={a.name} value={a.name}>
                  {a.displayName}
                  {a.isSuggested ? " (suggested)" : ""}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-[10px] font-medium text-muted-foreground">
              Direction
            </label>
            <div className="flex gap-2">
              {(["ASC", "DESC"] as const).map((dir) => (
                <button
                  key={dir}
                  type="button"
                  onClick={() => onSortDirectionChange(dir)}
                  className={`rounded-md border px-3 py-1 text-xs font-medium transition ${
                    sortDirection === dir
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-card text-muted-foreground hover:border-primary/40"
                  }`}
                >
                  {dir === "ASC" ? "Ascending" : "Descending"}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
