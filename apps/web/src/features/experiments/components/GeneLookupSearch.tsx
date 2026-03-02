import { useMemo } from "react";
import { Lightbulb, Search } from "lucide-react";

interface GeneLookupSearchProps {
  query: string;
  organism: string;
  onQueryChange: (query: string) => void;
  onOrganismChange: (organism: string) => void;
}

export function GeneLookupSearch({
  query,
  organism,
  onQueryChange,
  onOrganismChange,
}: GeneLookupSearchProps) {
  const searchHint = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return null;
    if (/^[a-z]{2,6}\d/i.test(q) && !q.includes("_")) {
      return "Looks like a gene ID prefix \u2014 results include wildcard matches across the database.";
    }
    if (q.includes("_") && /^[a-z0-9]+_/i.test(q)) {
      return "Searching by gene ID prefix \u2014 matching genes will appear at the top.";
    }
    return null;
  }, [query]);

  return (
    <div className="space-y-2 border-b border-border p-3">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Gene name, ID prefix, product, or keyword\u2026"
            className="w-full rounded-md border border-border py-1.5 pl-7 pr-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
            autoFocus
          />
        </div>
      </div>
      <div>
        <input
          type="text"
          value={organism}
          onChange={(e) => onOrganismChange(e.target.value)}
          placeholder="Filter by organism (optional)\u2026"
          className="w-full rounded-md border border-border px-2.5 py-1.5 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>
      {searchHint && (
        <div className="flex items-start gap-1.5 rounded bg-primary/5/80 px-2.5 py-1.5">
          <Lightbulb className="mt-0.5 h-3 w-3 shrink-0 text-primary/60" />
          <span className="text-xs text-primary">{searchHint}</span>
        </div>
      )}
    </div>
  );
}
