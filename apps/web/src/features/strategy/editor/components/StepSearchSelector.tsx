"use client";

import type { RecordType, Search } from "@pathfinder/shared";
import type { StepKind } from "@pathfinder/shared";
import { VEUPATHDB_SITES } from "@pathfinder/shared";
import { normalizeRecordType } from "@/features/strategy/recordType";

function rewriteRelativeAssetUrls(html: string, origin: string): string {
  if (!html) return html;
  if (!origin) return html;
  const base = origin.replace(/\/$/, "");
  // Rewrite WDK-relative assets like /a/images/yes.gif to absolute site URLs.
  return html.replace(
    /(src|href)=(['"])(\/a\/[^'"]+)\2/gi,
    (_match, attr, quote, path) => `${attr}=${quote}${base}${path}${quote}`,
  );
}

type StepSearchSelectorProps = {
  siteId: string;
  stepType: StepKind;
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
  siteId,
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
  const siteOrigin =
    VEUPATHDB_SITES.find((s) => s.id === siteId)?.baseUrl || `https://${siteId}.org`;
  return (
    <>
      <div>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Record Type
        </label>
        <input
          value={recordTypeFilter}
          onChange={(event) => onRecordTypeFilterChange(event.target.value)}
          placeholder="Filter record types..."
          className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        {filteredRecordTypes.length > 0 ? (
          <div className="mt-2 max-h-40 w-full overflow-auto rounded-md border border-border bg-card p-2 text-sm">
            {filteredRecordTypes.map((option) => (
              <label
                key={option.name}
                className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 transition-colors duration-150 hover:bg-accent"
              >
                <input
                  type="radio"
                  name="record-type"
                  value={option.name}
                  checked={normalizedRecordTypeValue === option.name}
                  onChange={() => onRecordTypeValueChange(option.name)}
                  className="mt-0.5 h-3.5 w-3.5 border-input text-foreground"
                />
                <div>
                  <div className="font-medium text-foreground">
                    {option.displayName || option.name}
                  </div>
                  <div className="text-xs text-muted-foreground">{option.name}</div>
                </div>
              </label>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-xs text-muted-foreground">
            No record types available.
          </p>
        )}
      </div>
      <div className="relative">
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {stepType === "transform" ? "Transform Name" : "Search Name"}
        </label>
        <input
          value={editableSearchName}
          onChange={(event) => onSearchNameChange(event.target.value)}
          disabled={isLoadingSearches || searchOptions.length === 0}
          placeholder="Search..."
          className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:bg-muted disabled:text-muted-foreground"
        />
        {filteredSearchOptions.length > 0 && (
          <div className="mt-2 max-h-56 w-full overflow-auto rounded-md border border-border bg-card p-2 text-sm">
            {filteredSearchOptions.map((option) => (
              <label
                key={option.name}
                className="flex cursor-pointer items-start gap-2 rounded px-1 py-1 transition-colors duration-150 hover:bg-accent"
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
                        (recordOption) => recordOption.name === nextRecordType,
                      )
                    ) {
                      onRecordTypeValueChange(nextRecordType);
                    }
                  }}
                  className="mt-0.5 h-3.5 w-3.5 border-input text-foreground"
                />
                <div>
                  <div className="font-medium text-foreground">
                    {option.displayName || option.name}
                  </div>
                  <div className="text-xs text-muted-foreground">{option.name}</div>
                </div>
              </label>
            ))}
          </div>
        )}
        {selectedSearch && (
          <div className="mt-1 text-xs text-muted-foreground">
            <div
              className="[&_img]:inline-block [&_img]:align-middle [&_img]:!m-0 [&_img]:h-[12px] [&_img]:w-[12px]"
              dangerouslySetInnerHTML={{
                __html: rewriteRelativeAssetUrls(
                  selectedSearch.description || "No description available.",
                  siteOrigin,
                ),
              }}
            />
            <span className="text-muted-foreground">ID: {selectedSearch.name}</span>
          </div>
        )}
        {!selectedSearch && searchName && !isSearchNameAvailable && (
          <p className="mt-1 text-xs text-amber-600">
            This search is not available for the selected record type.
          </p>
        )}
        {!selectedSearch && searchOptions.length > 0 && (
          <p className="mt-1 text-xs text-muted-foreground">
            Pick a search to see its description and parameters.
          </p>
        )}
        {searchListError && (
          <p className="mt-1 text-xs text-destructive">{searchListError}</p>
        )}
        {!searchListError && isLoadingSearches && (
          <p className="mt-1 text-xs text-muted-foreground">Loading search list...</p>
        )}
      </div>
    </>
  );
}
