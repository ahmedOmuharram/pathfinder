"use client";

import type { RecordType, Search, Step } from "@pathfinder/shared";
import { normalizeRecordType } from "@/features/strategy/recordType";

type StepSearchSelectorProps = {
  stepType: Step["type"];
  recordTypeFilter: string;
  onRecordTypeFilterChange: (nextValue: string) => void;
  filteredRecordTypes: RecordType[];
  normalizedRecordTypeValue: string | null | undefined;
  onRecordTypeValueChange: (nextValue: string) => void;
  editableSearchName: string;
  onSearchNameChange: (nextValue: string) => void;
  isLoadingSearches: boolean;
  searchOptions: Search[];
  filteredSearchOptions: Search[];
  searchName: string;
  selectedSearch: Search | null;
  isSearchNameAvailable: boolean;
  searchListError: string | null;
  recordTypeValue: string | null | undefined;
  recordType: string | null;
  recordTypeOptions: RecordType[];
};

export function StepSearchSelector({
  stepType,
  recordTypeFilter,
  onRecordTypeFilterChange,
  filteredRecordTypes,
  normalizedRecordTypeValue,
  onRecordTypeValueChange,
  editableSearchName,
  onSearchNameChange,
  isLoadingSearches,
  searchOptions,
  filteredSearchOptions,
  searchName,
  selectedSearch,
  isSearchNameAvailable,
  searchListError,
  recordTypeValue,
  recordType,
  recordTypeOptions,
}: StepSearchSelectorProps) {
  return (
    <>
      <div>
        <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          Record Type
        </label>
        <input
          value={recordTypeFilter}
          onChange={(event) => onRecordTypeFilterChange(event.target.value)}
          placeholder="Filter record types..."
          className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-900 focus:border-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-200"
        />
        {filteredRecordTypes.length > 0 ? (
          <div className="mt-2 max-h-40 w-full overflow-auto rounded-md border border-slate-200 bg-white p-2 text-[12px]">
            {filteredRecordTypes.map((option) => (
              <label
                key={option.name}
                className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 hover:bg-slate-50"
              >
                <input
                  type="radio"
                  name="record-type"
                  value={option.name}
                  checked={normalizedRecordTypeValue === option.name}
                  onChange={() => onRecordTypeValueChange(option.name)}
                  className="mt-0.5 h-3.5 w-3.5 border-slate-300 text-slate-900"
                />
                <div>
                  <div className="font-medium text-slate-800">
                    {option.displayName || option.name}
                  </div>
                  <div className="text-[10px] text-slate-400">{option.name}</div>
                </div>
              </label>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-[11px] text-slate-500">No record types available.</p>
        )}
      </div>
      <div className="relative">
        <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
          {stepType === "transform" ? "Transform Name" : "Search Name"}
        </label>
        <input
          value={editableSearchName}
          onChange={(event) => onSearchNameChange(event.target.value)}
          disabled={isLoadingSearches || searchOptions.length === 0}
          placeholder="Search..."
          className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-900 focus:border-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-200 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
        />
        {filteredSearchOptions.length > 0 && (
          <div className="mt-2 max-h-56 w-full overflow-auto rounded-md border border-slate-200 bg-white p-2 text-[12px]">
            {filteredSearchOptions.map((option) => (
              <label
                key={option.name}
                className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 hover:bg-slate-50"
              >
                <input
                  type="radio"
                  name="search-name"
                  value={option.name}
                  checked={option.name === searchName}
                  onChange={() => {
                    onSearchNameChange(option.name);
                    const nextRecordType = normalizeRecordType(option.recordType);
                    const current = normalizeRecordType(recordTypeValue || recordType);
                    if (
                      nextRecordType &&
                      nextRecordType !== current &&
                      recordTypeOptions.some(
                        (recordOption) => recordOption.name === nextRecordType
                      )
                    ) {
                      onRecordTypeValueChange(nextRecordType);
                    }
                  }}
                  className="mt-0.5 h-3.5 w-3.5 border-slate-300 text-slate-900"
                />
                <div>
                  <div className="font-medium text-slate-800">
                    {option.displayName || option.name}
                  </div>
                  <div className="text-[10px] text-slate-400">{option.name}</div>
                </div>
              </label>
            ))}
          </div>
        )}
        {selectedSearch && (
          <div className="mt-1 text-[11px] text-slate-500">
            <div
              dangerouslySetInnerHTML={{
                __html: selectedSearch.description || "No description available.",
              }}
            />
            <span className="text-slate-400">ID: {selectedSearch.name}</span>
          </div>
        )}
        {!selectedSearch && searchName && !isSearchNameAvailable && (
          <p className="mt-1 text-[11px] text-amber-600">
            This search is not available for the selected record type.
          </p>
        )}
        {!selectedSearch && searchOptions.length > 0 && (
          <p className="mt-1 text-[11px] text-slate-500">
            Pick a search to see its description and parameters.
          </p>
        )}
        {searchListError && (
          <p className="mt-1 text-[11px] text-red-500">{searchListError}</p>
        )}
        {!searchListError && isLoadingSearches && (
          <p className="mt-1 text-[11px] text-slate-500">
            Loading search list...
          </p>
        )}
      </div>
    </>
  );
}
