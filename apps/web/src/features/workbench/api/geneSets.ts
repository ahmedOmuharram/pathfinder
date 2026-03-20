/**
 * Gene set API client — CRUD and set-operation endpoints.
 */

import type { EnrichmentResult } from "@pathfinder/shared";
import { requestJson } from "@/lib/api/http";
import type { GeneSet } from "../store";
import type { StepParameters } from "@/lib/strategyGraph/types";

// ---------------------------------------------------------------------------
// Request / response types
// ---------------------------------------------------------------------------

export interface CreateGeneSetRequest {
  name: string;
  source: GeneSet["source"];
  geneIds: string[];
  siteId: string;
  wdkStrategyId?: number;
  wdkStepId?: number;
  searchName?: string;
  recordType?: string;
  parameters?: StepParameters;
}

export interface SetOperationRequest {
  operation: "intersect" | "union" | "minus";
  setAId: string;
  setBId: string;
  name: string;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Create a new gene set. */
export function createGeneSet(req: CreateGeneSetRequest): Promise<GeneSet> {
  return requestJson<GeneSet>("/api/v1/gene-sets", {
    method: "POST",
    body: req,
  });
}

/** List gene sets, optionally filtered by site. */
export function listGeneSets(siteId?: string): Promise<GeneSet[]> {
  return requestJson<GeneSet[]>("/api/v1/gene-sets", {
    ...(siteId != null && siteId !== "" ? { query: { siteId } } : {}),
  });
}

/** Delete a gene set by ID. */
export function deleteGeneSet(id: string): Promise<void> {
  return requestJson<void>(`/api/v1/gene-sets/${id}`, {
    method: "DELETE",
  });
}

/** Perform a set operation (intersect, union, minus) across gene sets. */
export function performSetOperation(req: SetOperationRequest): Promise<GeneSet> {
  return requestJson<GeneSet>("/api/v1/gene-sets/operations", {
    method: "POST",
    body: req,
  });
}

/** Run enrichment analysis on a gene set. */
export function enrichGeneSet(
  id: string,
  types: string[],
): Promise<EnrichmentResult[]> {
  return requestJson<EnrichmentResult[]>(`/api/v1/gene-sets/${id}/enrich`, {
    method: "POST",
    body: { enrichmentTypes: types },
  });
}

// ---------------------------------------------------------------------------
// Strategy-sourced gene set creation
// ---------------------------------------------------------------------------

export interface CreateFromStrategyArgs {
  name: string;
  siteId: string;
  wdkStrategyId: number;
  wdkStepId?: number;
  searchName?: string;
  recordType?: string;
  parameters?: StepParameters;
  geneIds?: string[];
}

/**
 * Create a gene set from a built WDK strategy.
 *
 * Sends the strategy metadata along with whatever gene IDs are available.
 * When `geneIds` is empty the backend will still persist the set; enrichment
 * can use the `wdkStepId` directly.
 */
export function createGeneSetFromStrategy(
  args: CreateFromStrategyArgs,
): Promise<GeneSet> {
  const req: CreateGeneSetRequest = {
    name: args.name,
    source: "strategy",
    geneIds: args.geneIds ?? [],
    siteId: args.siteId,
    wdkStrategyId: args.wdkStrategyId,
  };
  if (args.wdkStepId != null) req.wdkStepId = args.wdkStepId;
  if (args.searchName != null) req.searchName = args.searchName;
  if (args.recordType != null) req.recordType = args.recordType;
  if (args.parameters != null) req.parameters = args.parameters;
  return createGeneSet(req);
}
