import type { Classification } from "@pathfinder/shared";

export interface RecordAttribute {
  name: string;
  displayName: string;
  help?: string | null;
  type?: string | null;
  isDisplayable?: boolean;
  isSortable?: boolean;
  isSuggested?: boolean;
}

export interface WdkRecord {
  id: { name: string; value: string }[];
  attributes: Record<string, string | null>;
  _classification?: Classification | null;
}

export interface RecordsResponse {
  records: WdkRecord[];
  meta: {
    totalCount: number;
    displayTotalCount: number;
    responseCount: number;
    pagination: { offset: number; numRecords: number };
    attributes: string[];
    tables: string[];
  };
}

/**
 * Full record detail returned by the `/results/record` endpoint.
 */
export interface RecordDetail {
  id?: { name: string; value: string }[];
  attributes?: Record<string, string | null>;
  attributeNames?: Record<string, string>;
  tables?: Record<string, unknown[]>;
  recordType?: string;
}

/**
 * Histogram bin shape returned inside distribution responses.
 */
export interface DistributionHistogramBin {
  binLabel?: string;
  binStart?: string;
  value: number;
}

/**
 * Distribution response from the `/results/distributions/:attr` endpoint.
 *
 * May be a flat `{ [value]: count }` map, or contain a `histogram` array,
 * or wrap the map inside a `distribution` field.
 */
export interface DistributionResponse {
  histogram?: DistributionHistogramBin[];
  distribution?: Record<string, number>;
  total?: number;
  attributeName?: string;
  [key: string]: unknown;
}
