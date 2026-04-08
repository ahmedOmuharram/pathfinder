import { QueryClient } from "@tanstack/react-query";

import { APIError } from "@/lib/api/http";
import { modelCatalogOptions } from "@/lib/api/models";
import { sitesOptions } from "@/lib/api/sites";

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: (failureCount, error) => {
          if (error instanceof APIError && error.status >= 400 && error.status < 500) {
            return false;
          }
          return failureCount < 2;
        },
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

export function getQueryClient(): QueryClient {
  if (typeof window === "undefined") {
    return makeQueryClient();
  }
  if (browserQueryClient == null) {
    browserQueryClient = makeQueryClient();
    void browserQueryClient.prefetchQuery(sitesOptions());
    void browserQueryClient.prefetchQuery(modelCatalogOptions());
  }
  return browserQueryClient;
}
