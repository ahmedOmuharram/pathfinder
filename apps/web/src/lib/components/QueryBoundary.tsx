"use client";

import { Suspense } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";
import { DefaultSpinner } from "./DefaultSpinner";
import { DefaultQueryError } from "./DefaultQueryError";

interface QueryBoundaryProps {
  children: React.ReactNode;
  loadingFallback?: React.ReactNode;
  ErrorFallback?: React.ComponentType<FallbackProps>;
  resetKeys?: unknown[];
}

export function QueryBoundary({
  children,
  loadingFallback = <DefaultSpinner />,
  ErrorFallback = DefaultQueryError,
  resetKeys,
}: QueryBoundaryProps) {
  return (
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      {...(resetKeys !== undefined ? { resetKeys } : {})}
    >
      <Suspense fallback={loadingFallback}>
        {children}
      </Suspense>
    </ErrorBoundary>
  );
}
