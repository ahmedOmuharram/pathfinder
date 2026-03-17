/**
 * Collapsible wrapper for params in the "advancedParams" WDK group.
 * Closed by default. Shows param count and validation indicators.
 */

import type { ReactNode } from "react";

interface AdvancedParamsGroupProps {
  children: ReactNode;
  count: number;
  hasErrors?: boolean;
}

export function AdvancedParamsGroup({
  children,
  count,
  hasErrors = false,
}: AdvancedParamsGroupProps) {
  if (count === 0) return null;
  return (
    <details
      className={`rounded-lg border bg-card px-3 py-2 ${
        hasErrors ? "border-destructive/30" : "border-border"
      }`}
    >
      <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-muted-foreground select-none">
        Advanced Parameters ({count})
        {hasErrors && (
          <span className="ml-2 text-destructive" aria-label="has errors">
            !
          </span>
        )}
      </summary>
      <div className="mt-2 space-y-3">{children}</div>
    </details>
  );
}
