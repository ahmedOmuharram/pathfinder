"use client";

import { useAuiState, type MessageState } from "@assistant-ui/react";
import { Shimmer } from "@/components/ai-elements/shimmer";

const DEFAULT_LABEL = "Thinking...";

function readTurnStatus(part: { type: string; data?: unknown }): string | null {
  if (part.type !== "data-turn-status") return null;
  const data = part.data;
  if (data == null || typeof data !== "object") return null;
  const label = (data as { label?: unknown }).label;
  return typeof label === "string" && label.length > 0 ? label : null;
}

/**
 * Returns the label string to show, or `null` to hide the placeholder.
 * Returns a primitive so useAuiState's identity check doesn't cause a
 * re-render loop (React #185).
 */
function selectPlaceholderLabel(m: MessageState | undefined): string | null {
  if (m == null || m.status?.type !== "running") return null;
  let label = DEFAULT_LABEL;
  for (const part of m.content) {
    if (part.type === "text" && part.text.length > 0) return null;
    if (part.type === "reasoning" && part.text.length > 0) return null;
    if (part.type === "tool-call") return null;
    const statusLabel = readTurnStatus(part);
    if (statusLabel !== null) {
      label = statusLabel;
      continue;
    }
    if (part.type === "data") return null;
  }
  return label;
}

export function AssistantThinkingPlaceholder() {
  const label = useAuiState((s) => selectPlaceholderLabel(s.message));
  if (typeof label !== "string") return null;
  return (
    <Shimmer as="span" className="text-sm font-medium" duration={1.2}>
      {label}
    </Shimmer>
  );
}
