import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, createElement } from "react";
import type { ReactNode } from "react";
import { ErrorBoundary } from "react-error-boundary";

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
        staleTime: 0,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function createTestWrapper(): {
  queryClient: QueryClient;
  Wrapper: ({ children }: { children: ReactNode }) => ReactNode;
} {
  const queryClient = createTestQueryClient();
  function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  }
  return { queryClient, Wrapper };
}

/**
 * Wrapper for testing hooks that use useSuspenseQuery.
 * Includes Suspense + ErrorBoundary so the hook can suspend/throw without crashing the test.
 */
export function createSuspenseWrapper(): {
  queryClient: QueryClient;
  Wrapper: ({ children }: { children: ReactNode }) => ReactNode;
} {
  const queryClient = createTestQueryClient();
  function Wrapper({ children }: { children: ReactNode }) {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(
        ErrorBoundary,
        {
          fallbackRender: ({ error }: { error: unknown }) =>
            createElement(
              "div",
              { "data-testid": "error-boundary" },
              error instanceof Error ? error.message : String(error),
            ),
        },
        createElement(
          Suspense,
          {
            fallback: createElement(
              "div",
              { "data-testid": "suspense-fallback" },
              "Loading...",
            ),
          },
          children,
        ),
      ),
    );
  }
  return { queryClient, Wrapper };
}
