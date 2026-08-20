"use client";

import { useAuiState } from "@assistant-ui/react";

import { Shimmer } from "@/components/ai-elements/shimmer";
import { ProviderIcon } from "@/lib/components/ProviderIcon";
import { isLocalProvider, parseModelString } from "@/lib/models/providerMeta";

const DEFAULT_LABEL = "Thinking...";

interface TurnStatusData {
  label?: unknown;
  model?: unknown;
}

interface StatusPart {
  type: string;
  name?: string | undefined;
  data?: unknown;
}

interface StatusCarrier {
  status?: { type: string } | undefined;
  content: readonly StatusPart[];
}

function turnStatusData(part: StatusPart): TurnStatusData | null {
  const isTurnStatus =
    part.type === "data-turn-status" ||
    (part.type === "data" &&
      (part.name === "turn-status" || part.name === "data-turn-status"));
  if (!isTurnStatus) return null;
  const data = part.data;
  if (data == null || typeof data !== "object") return null;
  return data as TurnStatusData;
}

// Selectors return primitives so useAuiState's identity check doesn't loop
// (React #185). The status stays visible for the whole running turn, tracking
// the latest data-turn-status label instead of hiding once tool calls or text
// start.
export function selectStatusLabel(m: StatusCarrier | undefined): string | null {
  if (m == null || m.status?.type !== "running") return null;
  let label = DEFAULT_LABEL;
  for (const part of m.content) {
    const data = turnStatusData(part);
    if (data !== null && typeof data.label === "string" && data.label.length > 0) {
      label = data.label;
    }
  }
  return label;
}

function selectStatusModel(m: StatusCarrier | undefined): string | null {
  if (m == null || m.status?.type !== "running") return null;
  let model: string | null = null;
  for (const part of m.content) {
    const data = turnStatusData(part);
    if (data !== null && typeof data.model === "string" && data.model.length > 0) {
      model = data.model;
    }
  }
  return model;
}

export function AssistantThinkingPlaceholder() {
  const label = useAuiState((s) => selectStatusLabel(s.message));
  const model = useAuiState((s) => selectStatusModel(s.message));
  if (typeof label !== "string") return null;
  const provider = model !== null ? parseModelString(model).provider : null;
  return (
    <div data-testid="assistant-status" className="flex items-center gap-2 py-0.5">
      {provider !== null && !isLocalProvider(provider) && (
        <ProviderIcon
          provider={provider}
          size={14}
          className="shrink-0 text-muted-foreground"
        />
      )}
      <Shimmer as="span" className="text-sm font-medium" duration={1.2}>
        {label}
      </Shimmer>
    </div>
  );
}
