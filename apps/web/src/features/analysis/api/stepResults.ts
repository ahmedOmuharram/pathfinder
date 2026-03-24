/**
 * Unified step result browsing API.
 *
 * Provides a single set of functions for attributes, records, distributions,
 * analyses, and strategy access — used identically for both experiments and
 * gene sets via the `EntityRef` discriminated union.
 */

import type { z } from "zod";
import { requestJson } from "@/lib/api/http";
import {
  AttributesResponseSchema,
  RecordAttributeSchema,
  RecordsResponseSchema,
  RecordDetailSchema,
  DistributionResponseSchema,
} from "@/lib/api/schemas/step-results";

export type RecordAttribute = z.infer<typeof RecordAttributeSchema>;
export type RecordsResponse = z.infer<typeof RecordsResponseSchema>;
export type RecordDetail = z.infer<typeof RecordDetailSchema>;
export type DistributionResponse = z.infer<typeof DistributionResponseSchema>;

export type EntityRef =
  | { type: "experiment"; id: string }
  | { type: "gene-set"; id: string };

function basePath(ref: EntityRef): string {
  return ref.type === "experiment"
    ? `/api/v1/experiments/${ref.id}`
    : `/api/v1/gene-sets/${ref.id}`;
}

export function getAttributes(ref: EntityRef) {
  return requestJson(AttributesResponseSchema, `${basePath(ref)}/results/attributes`);
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
) {
  const query: Record<string, string> = {};
  if (opts?.offset != null) query["offset"] = String(opts.offset);
  if (opts?.limit != null) query["limit"] = String(opts.limit);
  if (opts?.sort != null && opts.sort !== "") query["sort"] = opts.sort;
  if (opts?.dir != null) query["dir"] = opts.dir;
  if (opts?.attributes != null && opts.attributes.length > 0)
    query["attributes"] = opts.attributes.join(",");
  if (opts?.filterAttribute != null && opts.filterAttribute !== "")
    query["filterAttribute"] = opts.filterAttribute;
  if (opts?.filterValue != null) query["filterValue"] = opts.filterValue;
  return requestJson(RecordsResponseSchema, `${basePath(ref)}/results/records`, {
    query,
  });
}

export function getRecordDetail(
  ref: EntityRef,
  primaryKey: { name: string; value: string }[],
) {
  return requestJson(RecordDetailSchema, `${basePath(ref)}/results/record`, {
    method: "POST",
    body: { primaryKey },
  });
}

export function getDistribution(ref: EntityRef, attributeName: string) {
  return requestJson(
    DistributionResponseSchema,
    `${basePath(ref)}/results/distributions/${encodeURIComponent(attributeName)}`,
  );
}
