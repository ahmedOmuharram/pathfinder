import type { RecordType, Search } from "@pathfinder/shared";

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
    <div className="space-y-4">
      <div>
        <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Record Type
        </label>
        <select
          value={selectedRecordType}
          onChange={(e) => onRecordTypeChange(e.target.value)}
          className="w-full rounded-md border border-slate-200 px-3 py-2 text-[12px] text-slate-700 outline-none focus:border-slate-300"
        >
          {recordTypes.map((rt) => (
            <option key={rt.name} value={rt.name}>
              {rt.displayName} ({rt.name})
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Search
        </label>
        <input
          type="text"
          value={searchFilter}
          onChange={(e) => onSearchFilterChange(e.target.value)}
          placeholder="Filter searches..."
          className="mb-2 w-full rounded-md border border-slate-200 px-3 py-1.5 text-[12px] outline-none placeholder:text-slate-400 focus:border-slate-300"
        />
        <div className="max-h-96 overflow-y-auto rounded-md border border-slate-200">
          {filteredSearches.map((s) => (
            <button
              key={s.name}
              type="button"
              onClick={() => onSearchChange(s.name)}
              className={`flex w-full flex-col px-3 py-2 text-left transition hover:bg-slate-50 ${
                selectedSearch === s.name
                  ? "bg-indigo-50 border-l-2 border-indigo-500"
                  : "border-b border-slate-100"
              }`}
            >
              <span className="text-[12px] font-medium text-slate-700">
                {s.displayName}
              </span>
              {s.description && (
                <span className="text-[10px] text-slate-500 line-clamp-2">
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
