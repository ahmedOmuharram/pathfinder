/**
 * Unified step result browsing API.
 *
 * Provides a single set of functions for attributes, records, distributions,
 * analyses, and strategy access — used identically for both experiments and
 * gene sets via the `EntityRef` discriminated union.
 */

import { requestJson } from "@/lib/api/http";
import type {
  RecordAttribute,
  RecordsResponse,
} from "@/features/workbench/api/experiments";

export type { RecordAttribute, RecordsResponse };

export type EntityRef =
  | { type: "experiment"; id: string }
  | { type: "gene-set"; id: string };

function basePath(ref: EntityRef): string {
  return ref.type === "experiment"
    ? `/api/v1/experiments/${ref.id}`
    : `/api/v1/gene-sets/${ref.id}`;
}

export function getAttributes(
  ref: EntityRef,
): Promise<{ attributes: RecordAttribute[]; recordType: string }> {
  return requestJson(`${basePath(ref)}/results/attributes`);
}

export function getRecords(
  ref: EntityRef,
  opts?: {
    offset?: number;
    limit?: number;
    sort?: string;
    dir?: "ASC" | "DESC";
    attributes?: string[];
    filterAttribute?: string;
    filterValue?: string;
  },
): Promise<RecordsResponse> {
  const query: Record<string, string> = {};
  if (opts?.offset != null) query.offset = String(opts.offset);
  if (opts?.limit != null) query.limit = String(opts.limit);
  if (opts?.sort) query.sort = opts.sort;
  if (opts?.dir) query.dir = opts.dir;
  if (opts?.attributes?.length) query.attributes = opts.attributes.join(",");
  if (opts?.filterAttribute) query.filterAttribute = opts.filterAttribute;
  if (opts?.filterValue != null) query.filterValue = opts.filterValue;
  return requestJson<RecordsResponse>(`${basePath(ref)}/results/records`, {
    query,
  });
}

export function getRecordDetail(
  ref: EntityRef,
  primaryKey: { name: string; value: string }[],
): Promise<Record<string, unknown>> {
  return requestJson(`${basePath(ref)}/results/record`, {
    method: "POST",
    body: { primaryKey },
  });
}

export function getDistribution(
  ref: EntityRef,
  attributeName: string,
): Promise<Record<string, unknown>> {
  return requestJson(
    `${basePath(ref)}/results/distributions/${encodeURIComponent(attributeName)}`,
  );
}
