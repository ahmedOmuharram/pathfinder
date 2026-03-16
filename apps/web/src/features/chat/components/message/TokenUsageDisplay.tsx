"use client";

import { useState } from "react";
import type { TokenUsage } from "@pathfinder/shared";
import { useSettingsStore } from "@/state/useSettingsStore";
import { formatCompact, formatCost } from "@/lib/utils/format";

interface TokenUsageDisplayProps {
  usage: TokenUsage;
}

export function TokenUsageDisplay({ usage }: TokenUsageDisplayProps) {
  const show = useSettingsStore((s) => s.showTokenUsage);
  const [expanded, setExpanded] = useState(false);
  const catalog = useSettingsStore((s) => s.modelCatalog);

  if (!show || !usage.totalTokens) return null;

  // Guard against old messages missing new fields.
  const cachedTokens = usage.cachedTokens ?? 0;
  const llmCallCount = usage.llmCallCount ?? 0;
  const subPrompt = usage.subKaniPromptTokens ?? 0;
  const subCompletion = usage.subKaniCompletionTokens ?? 0;
  const subCalls = usage.subKaniCallCount ?? 0;
  const cost = usage.estimatedCostUsd ?? 0;
  const modelId = usage.modelId ?? "";

  const modelName = catalog.find((m) => m.id === modelId)?.name ?? modelId;
  const cacheHitRate =
    usage.promptTokens > 0
      ? ((cachedTokens / usage.promptTokens) * 100).toFixed(1)
      : "0";
  const subTotal = subPrompt + subCompletion;

  return (
    <div className="mt-1.5">
      {/* Collapsed summary */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-[10px] text-muted-foreground/60 hover:text-muted-foreground/80 transition-colors"
      >
        <span>
          {formatCompact(usage.promptTokens)} in +{" "}
          {formatCompact(usage.completionTokens)} out
        </span>
        <span className="text-muted-foreground/40">&middot;</span>
        <span className="text-amber-500/70">~{formatCost(cost)}</span>
        <span className="text-muted-foreground/40">&middot;</span>
        <span className="text-primary/60">
          {expanded ? "hide \u25B4" : "details \u25BE"}
        </span>
      </button>

      {/* Expanded detail panel */}
      {expanded && (
        <div className="mt-1.5 rounded-md bg-muted/30 border border-border/40 p-3 text-[10px] text-muted-foreground/70 leading-relaxed">
          <div className="grid grid-cols-2 gap-x-6 gap-y-0.5">
            <div>
              Input (prompt):{" "}
              <span className="text-foreground/70">
                {usage.promptTokens.toLocaleString()}
              </span>
            </div>
            <div>
              Output (completion):{" "}
              <span className="text-foreground/70">
                {usage.completionTokens.toLocaleString()}
              </span>
            </div>
            <div className="col-span-2 text-foreground/50">
              Total: {usage.totalTokens.toLocaleString()} tokens
            </div>
            <div>
              Cached tokens:{" "}
              <span className="text-foreground/70">
                {cachedTokens.toLocaleString()}
              </span>
            </div>
            <div>
              Cache hit rate:{" "}
              <span className="text-foreground/70">{cacheHitRate}%</span>
            </div>
            <div>
              LLM calls: <span className="text-foreground/70">{llmCallCount}</span>
            </div>
            <div>
              Tool calls:{" "}
              <span className="text-foreground/70">{usage.toolCallCount}</span>
            </div>
            {subTotal > 0 && (
              <>
                <div>
                  Sub-agent in:{" "}
                  <span className="text-foreground/70">
                    {subPrompt.toLocaleString()}
                  </span>
                </div>
                <div>
                  Sub-agent out:{" "}
                  <span className="text-foreground/70">
                    {subCompletion.toLocaleString()}
                  </span>
                </div>
                <div>
                  Sub-agent calls:{" "}
                  <span className="text-foreground/70">{subCalls}</span>
                </div>
              </>
            )}
            {modelName && (
              <div>
                Model: <span className="text-foreground/70">{modelName}</span>
              </div>
            )}
          </div>
          {cost > 0 && (
            <div className="mt-2 pt-2 border-t border-border/30">
              <span className="text-amber-500/70">Cost: {formatCost(cost)}</span>
              {cachedTokens > 0 && (
                <span className="ml-2 text-emerald-500/60">
                  (includes cache savings)
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
