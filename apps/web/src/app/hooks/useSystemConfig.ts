"use client";

import { useSuspenseQuery } from "@tanstack/react-query";
import { systemConfigOptions } from "@/lib/api/health";

/**
 * Checks whether the backend has at least one LLM provider configured.
 * Uses useSuspenseQuery — suspends until config loads.
 * Errors caught by nearest ErrorBoundary (app shell).
 */
export function useSystemConfig(): {
  setupRequired: boolean;
  retry: () => void;
} {
  const { data, refetch } = useSuspenseQuery(systemConfigOptions());
  const setupRequired = data.llmConfigured === false;
  return { setupRequired, retry: () => { void refetch(); } };
}
