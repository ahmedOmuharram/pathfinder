"use client";

import { useAuiState, type MessageState } from "@assistant-ui/react";
import type { DataLeadUsagePayload } from "@pathfinder/shared";
import type { ReactElement } from "react";

import { ProviderIcon } from "@/lib/components/ProviderIcon";
import { PROVIDER_LABELS, parseModelString } from "@/lib/models/providerMeta";
import { formatUsage } from "@/lib/utils/usageFormat";

function isLeadUsagePart(part: { type: string; name?: string }): boolean {
  return (
    part.type === "data-lead-usage" ||
    (part.type === "data" && part.name === "lead-usage")
  );
}

// Returns a primitive ("modelId\ttokens\tcostUsd") so useAuiState's identity
// check doesn't loop (React #185). A fresh object here re-renders forever.
export function selectLeadUsage(m: MessageState | undefined): string | null {
  if (m?.role !== "assistant") return null;
  for (let i = m.content.length - 1; i >= 0; i -= 1) {
    const part = m.content[i];
    if (part === undefined || !isLeadUsagePart(part)) continue;
    const data = (part as { data?: DataLeadUsagePayload }).data;
    if (data === undefined) continue;
    return `${data.modelId ?? ""}\t${data.tokens ?? 0}\t${data.costUsd ?? "0"}`;
  }
  return null;
}

export function ModelBadge(): ReactElement | null {
  const raw = useAuiState((s) => selectLeadUsage(s.message));
  if (raw === null) return null;
  const [modelId = "", tokensRaw = "0", costUsd = "0"] = raw.split("\t");
  if (modelId === "") return null;
  const tokens = Number(tokensRaw);
  const { provider, model } = parseModelString(modelId);
  const label = provider !== null ? PROVIDER_LABELS[provider] : "Model";
  return (
    <div
      data-testid="model-badge"
      className="inline-flex items-center gap-1.5 self-start rounded-full border border-border bg-muted/50 px-2 py-0.5 text-[11px] text-muted-foreground"
    >
      {provider !== null && (
        <ProviderIcon provider={provider} size={12} className="shrink-0" />
      )}
      <span className="font-medium text-foreground">{label}</span>
      {model !== "" && (
        <>
          <span aria-hidden>·</span>
          <span className="font-mono">{model}</span>
        </>
      )}
      {tokens > 0 && (
        <>
          <span aria-hidden>·</span>
          <span className="font-mono tabular-nums">{formatUsage(tokens, costUsd)}</span>
        </>
      )}
    </div>
  );
}
