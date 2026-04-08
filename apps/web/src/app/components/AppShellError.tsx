"use client";

import { useQueryClient } from "@tanstack/react-query";
import type { FallbackProps } from "react-error-boundary";
import { ApiErrorScreen } from "./ApiErrorScreen";

export function AppShellError({ error, resetErrorBoundary }: FallbackProps) {
  const queryClient = useQueryClient();

  function handleRetry() {
    void queryClient.resetQueries({ predicate: (q) => q.state.status === "error" });
    resetErrorBoundary();
  }

  const message = error instanceof Error ? error.message : "An unexpected error occurred.";
  return <ApiErrorScreen error={message} onRetry={handleRetry} />;
}
