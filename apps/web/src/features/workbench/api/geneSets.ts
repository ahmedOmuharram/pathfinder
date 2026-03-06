/**
 * Gene set API client — CRUD and set-operation endpoints.
 */

import type { EnrichmentResult } from "@pathfinder/shared";
import { requestJson } from "@/lib/api/http";
import type { GeneSet } from "../store";

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
  parameters?: Record<string, unknown>;
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
    query: siteId ? { siteId } : undefined,
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
// Gene ID resolution / verification
// ---------------------------------------------------------------------------

export interface ResolvedGene {
  geneId: string;
  displayName: string;
  organism: string;
  product: string;
  geneName: string;
  geneType: string;
  location: string;
}

export interface GeneResolveResult {
  resolved: ResolvedGene[];
  unresolved: string[];
}

/** Resolve gene IDs against the WDK to check validity and get metadata. */
export function resolveGeneIds(
  siteId: string,
  geneIds: string[],
): Promise<GeneResolveResult> {
  return requestJson<GeneResolveResult>(`/api/v1/sites/${siteId}/genes/resolve`, {
    method: "POST",
    body: { geneIds },
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
  parameters?: Record<string, unknown>;
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
  return createGeneSet({
    name: args.name,
    source: "strategy",
    geneIds: args.geneIds ?? [],
    siteId: args.siteId,
    wdkStrategyId: args.wdkStrategyId,
    wdkStepId: args.wdkStepId,
    searchName: args.searchName,
    recordType: args.recordType,
    parameters: args.parameters,
  });
}
