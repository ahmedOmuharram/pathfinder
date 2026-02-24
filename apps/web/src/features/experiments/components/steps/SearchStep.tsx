import type { RecordType, Search } from "@pathfinder/shared";
import { Label } from "@/lib/components/ui/Label";
import { Input } from "@/lib/components/ui/Input";
import { cn } from "@/lib/utils/cn";

interface SearchStepProps {
  recordTypes: RecordType[];
  selectedRecordType: string;
  onRecordTypeChange: (rt: string) => void;
  filteredSearches: Search[];
  searchFilter: string;
  onSearchFilterChange: (f: string) => void;
  selectedSearch: string;
  onSearchChange: (s: string) => void;
}

export function SearchStep({
  recordTypes,
  selectedRecordType,
  onRecordTypeChange,
  filteredSearches,
  searchFilter,
  onSearchFilterChange,
  selectedSearch,
  onSearchChange,
}: SearchStepProps) {
  return (
    <div className="space-y-5">
      <div>
        <Label className="mb-1.5 block">Record Type</Label>
        <select
          value={selectedRecordType}
          onChange={(e) => onRecordTypeChange(e.target.value)}
          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          {recordTypes.map((rt) => (
            <option key={rt.name} value={rt.name}>
              {rt.displayName} ({rt.name})
            </option>
          ))}
        </select>
      </div>

      <div>
        <Label className="mb-1.5 block">Search</Label>
        <Input
          type="text"
          value={searchFilter}
          onChange={(e) => onSearchFilterChange(e.target.value)}
          placeholder="Filter searches..."
          className="mb-2"
        />
        <div className="max-h-96 overflow-y-auto rounded-lg border border-border">
          {filteredSearches.map((s) => (
            <button
              key={s.name}
              type="button"
              onClick={() => onSearchChange(s.name)}
              className={cn(
                "flex w-full flex-col px-3 py-2.5 text-left transition-all duration-150",
                selectedSearch === s.name
                  ? "bg-primary/5 border-l-2 border-l-primary"
                  : "border-b border-border hover:bg-accent",
              )}
            >
              <span className="text-sm font-medium text-foreground">
                {s.displayName}
              </span>
              {s.description && (
                <span className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                  {s.description}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
