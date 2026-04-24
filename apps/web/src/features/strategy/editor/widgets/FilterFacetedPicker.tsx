"use client";

/**
 * Faceted picker for FilterParamNew when the backend surfaces ontology
 * metadata on the spec. Renders an Accordion per leaf ontology field,
 * dispatching by field `type` (string / number / date / longitude /
 * multiFilter) to the appropriate input primitive in
 * `FilterFacetSubcomponents.tsx`.
 *
 * The widget reads/writes the raw WDK FilterParamNew JSON shape:
 *   { filters: Array<{ field, type, isRange?, includeUnknown?, value }> }
 *
 * Backed by `filterParamLogic` for parsing/encoding.
 */

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import {
  type FilterEntry,
  type FilterValueObject,
  EMPTY_FILTER_VALUE,
  fieldTypeLabel,
  summarizeFilterValue,
} from "./filterParamLogic";
import { OntologySchema, type OntologyTerm } from "./ontologyTypes";
import {
  NumericRangeFacet,
  DateRangeFacet,
  MultiPickFacet,
  StringFacet,
  type FacetEditorProps,
} from "./FilterFacetSubcomponents";

interface FilterFacetedPickerProps {
  /** Ontology metadata as surfaced by the backend (`spec.ontology`). */
  ontology: unknown;
  value: FilterValueObject;
  onChange: (next: FilterValueObject) => void;
}

export function FilterFacetedPicker({
  ontology,
  value,
  onChange,
}: FilterFacetedPickerProps) {
  const parsed = OntologySchema.safeParse(ontology);
  if (!parsed.success) {
    return (
      <p className="text-xs text-amber-600">
        Ontology metadata is in an unexpected shape. Use Edit JSON to inspect.
      </p>
    );
  }

  const leaves = parsed.data.filter(
    (term) => term.type !== undefined && term.type !== "multiFilter",
  );

  if (leaves.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No editable ontology fields available.
      </p>
    );
  }

  const filtersByField = new Map(value.filters.map((f) => [f.field, f]));

  const setFilter = (term: OntologyTerm, next: FilterEntry | null) => {
    const remaining = value.filters.filter((f) => f.field !== term.term);
    onChange({
      filters: next === null ? remaining : [...remaining, next],
    });
  };

  const grouped = groupByParent(leaves);

  return (
    <Accordion
      type="multiple"
      data-testid="filter-faceted-picker"
      className="rounded-md border border-border"
    >
      {grouped.map(({ heading, terms }) => (
        <AccordionItem key={heading ?? "_root"} value={heading ?? "_root"}>
          <AccordionTrigger className="px-3 py-2 text-xs font-semibold uppercase tracking-wide">
            {heading ?? "Filters"}
            <ActiveCountBadge
              count={terms.filter((t) => filtersByField.has(t.term)).length}
            />
          </AccordionTrigger>
          <AccordionContent className="space-y-3 px-3 pb-3">
            {terms.map((term) => (
              <OntologyFieldEditor
                key={term.term}
                term={term}
                current={filtersByField.get(term.term) ?? null}
                onChange={(next) => setFilter(term, next)}
              />
            ))}
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}

function ActiveCountBadge({ count }: { count: number }) {
  if (count === 0) return null;
  return (
    <Badge variant="secondary" className="ml-auto h-5 px-2 text-[10px]">
      {count} active
    </Badge>
  );
}

function groupByParent(
  leaves: OntologyTerm[],
): Array<{ heading: string | null; terms: OntologyTerm[] }> {
  const buckets = new Map<string | null, OntologyTerm[]>();
  for (const t of leaves) {
    const key = t.parent ?? null;
    const arr = buckets.get(key) ?? [];
    arr.push(t);
    buckets.set(key, arr);
  }
  return [...buckets.entries()].map(([heading, terms]) => ({ heading, terms }));
}

function OntologyFieldEditor({ term, current, onChange }: FacetEditorProps) {
  const display = term.display ?? term.term;
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2">
        <label
          htmlFor={`facet-${term.term}`}
          className="text-xs font-medium text-foreground"
        >
          {display}
        </label>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {fieldTypeLabel({ field: term.term, type: term.type })}
        </span>
      </div>
      <FieldInput term={term} current={current} onChange={onChange} />
      {current !== null && (
        <p className="text-[10px] text-muted-foreground">
          Active: {summarizeFilterValue(current)}
        </p>
      )}
    </div>
  );
}

function FieldInput({ term, current, onChange }: FacetEditorProps) {
  if (term.type === "number" || term.type === "longitude") {
    return (
      <NumericRangeFacet term={term} current={current} onChange={onChange} />
    );
  }
  if (term.type === "date") {
    return <DateRangeFacet term={term} current={current} onChange={onChange} />;
  }
  if (term.type === "string") {
    if (term.values && term.values.length > 0) {
      return (
        <MultiPickFacet term={term} current={current} onChange={onChange} />
      );
    }
    return <StringFacet term={term} current={current} onChange={onChange} />;
  }
  return null;
}

// Re-exported so the parent FilterParam.tsx can decide between faceted vs JSON
// without importing logic from elsewhere.
export { EMPTY_FILTER_VALUE };
