"use client";

import { useStrategyGraphCtx } from "@/features/strategy/graph/StrategyGraphContext";

export function GraphWdkBadge() {
  const { isCompact, strategy, wdkUrlFallback } = useStrategyGraphCtx();

  if (isCompact) return null;

  const wdkStrategyId = strategy?.wdkStrategyId;
  const wdkUrl = strategy?.wdkUrl;

  if (
    wdkStrategyId == null &&
    (wdkUrl == null || wdkUrl === "") &&
    (wdkUrlFallback == null || wdkUrlFallback === "")
  )
    return null;

  const href = wdkUrl != null && wdkUrl !== "" ? wdkUrl : (wdkUrlFallback ?? undefined);

  return (
    <div className="pointer-events-auto absolute left-4 top-4 z-10 rounded-lg border border-border bg-card/90 px-2 py-1 text-xs text-muted-foreground shadow-sm backdrop-blur">
      {wdkStrategyId != null && (
        <div className="font-medium">
          Synced{" "}
          {href != null && href !== "" ? (
            <a
              className="font-mono text-foreground underline decoration-border underline-offset-4 transition-colors duration-150 hover:text-muted-foreground"
              href={href}
              target="_blank"
              rel="noreferrer"
            >
              #{wdkStrategyId}
            </a>
          ) : (
            <span className="font-mono">#{wdkStrategyId}</span>
          )}
        </div>
      )}

      {href != null && href !== "" && wdkStrategyId == null && (
        <a
          className="inline-block text-foreground underline decoration-border underline-offset-4 transition-colors duration-150 hover:text-muted-foreground"
          href={href}
          target="_blank"
          rel="noreferrer"
        >
          View
        </a>
      )}
    </div>
  );
}
