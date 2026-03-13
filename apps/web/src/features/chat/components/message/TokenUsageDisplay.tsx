"use client";

import type { TokenUsage } from "@pathfinder/shared";
import { useSettingsStore } from "@/state/useSettingsStore";

function fmt(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

interface TokenUsageDisplayProps {
  usage: TokenUsage;
  variant: "user" | "assistant";
}

export function TokenUsageDisplay({ usage, variant }: TokenUsageDisplayProps) {
  const show = useSettingsStore((s) => s.showTokenUsage);
  if (!show || usage.totalTokens === 0) return null;

  return (
    <div
      className={`flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-muted-foreground/60 ${
        variant === "user" ? "justify-end" : "justify-start"
      }`}
    >
      {variant === "user" ? (
        <>
          <span>{fmt(usage.promptTokens)} prompt tokens</span>
          {usage.registeredToolCount > 0 && (
            <>
              <span className="text-muted-foreground/40">|</span>
              <span>{usage.registeredToolCount} tools registered</span>
            </>
          )}
        </>
      ) : (
        <>
          <span>{fmt(usage.completionTokens)} completion tokens</span>
          {usage.toolCallCount > 0 && (
            <>
              <span className="text-muted-foreground/40">|</span>
              <span>{usage.toolCallCount} tool calls</span>
            </>
          )}
        </>
      )}
    </div>
  );
}
