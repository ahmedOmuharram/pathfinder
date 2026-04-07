/**
 * Broad prefix constants for TanStack Query cache invalidation.
 *
 * Exact query keys are co-located with their fetch functions via
 * `queryOptions()` in each API module. These prefixes exist solely
 * for broad invalidation (e.g. "invalidate all strategy queries").
 */
export const queryKeyPrefixes = {
  strategies: ["strategies"] as const,
  geneSets: ["gene-sets"] as const,
  experiments: ["experiments"] as const,
  sites: ["sites"] as const,
  auth: ["auth"] as const,
  models: ["models"] as const,
  config: ["config"] as const,
  genes: ["genes"] as const,
  controlSets: ["control-sets"] as const,
  tools: ["tools"] as const,
} as const;
