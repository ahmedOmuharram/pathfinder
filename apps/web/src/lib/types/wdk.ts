import type { Classification } from "@pathfinder/shared";

export interface RecordAttribute {
  name: string;
  displayName: string;
  help: string | null;
  type: string | null;
  isDisplayable: boolean;
  isSortable: boolean;
  isSuggested: boolean;
}

export interface WdkRecord {
  id: { name: string; value: string }[];
  attributes: Record<string, string | null>;
  _classification?: Classification | null | undefined;
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
  displayName: string;
  id: { name: string; value: string }[];
  recordClassName: string;
  attributes: Record<string, string | null>;
  attributeNames: Record<string, string>;
  tables: Record<string, unknown[]>;
  tableErrors: string[];
}

/**
 * Histogram bin shape returned inside distribution responses.
 */
export interface DistributionHistogramBin {
  value: number;
  binStart: string;
  binEnd: string;
  binLabel: string;
}

/**
 * Distribution statistics returned inside distribution responses.
 */
export interface DistributionStatistics {
  subsetSize: number;
  subsetMin: number | null;
  subsetMax: number | null;
  subsetMean: number | null;
  numVarValues: number;
  numDistinctValues: number;
  numDistinctEntityRecords: number;
  numMissingCases: number;
}

/**
 * Distribution response from the `/results/distributions/:attr` endpoint.
 */
export interface DistributionResponse {
  histogram: DistributionHistogramBin[];
  statistics: DistributionStatistics;
}
