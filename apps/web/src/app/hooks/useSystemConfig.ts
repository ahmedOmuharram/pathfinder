"use client";

import { useQuery } from "@tanstack/react-query";
import { systemConfigOptions } from "@/lib/api/health";

/**
 * Checks whether the backend has at least one LLM provider configured.
 *
 * Runs once on mount. When `setupRequired` is true the app should show
 * a blocking screen instead of the login form — there is no point
 * authenticating if the system cannot serve chat requests.
 */
export function useSystemConfig(): {
  configLoading: boolean;
  setupRequired: boolean;
  retry: () => void;
} {
  const { data, isPending, refetch } = useQuery(systemConfigOptions());

  // On error, setupRequired defaults to false — if the endpoint is
  // unreachable, the auth check will surface the API-down error instead.
  const setupRequired = data?.llmConfigured === false;

  return { configLoading: isPending, setupRequired, retry: () => { void refetch(); } };
}
