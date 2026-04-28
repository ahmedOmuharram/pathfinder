import { QueryCache, QueryClient } from "@tanstack/react-query";

import { APIError } from "@/lib/api/http";
import { modelCatalogOptions } from "@/lib/api/models";
import { sitesOptions } from "@/lib/api/sites";

export interface QueryErrorNotice {
  message: string;
  queryKey: readonly unknown[];
}

type NoticeHandler = (notice: QueryErrorNotice) => void;

let handler: NoticeHandler | null = null;

export function setQueryErrorHandler(next: NoticeHandler | null): void {
  handler = next;
}

function extractMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) return error.message || fallback;
  return fallback;
}

function isSilent(meta: Record<string, unknown> | undefined): boolean {
  return meta?.["silent"] === true;
}

function makeQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        if (isSilent(query.meta)) return;
        const message = extractMessage(error, "Request failed");
        handler?.({ message, queryKey: query.queryKey });
      },
    }),
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

export function __makeQueryClientForTests(): QueryClient {
  return makeQueryClient();
}

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
