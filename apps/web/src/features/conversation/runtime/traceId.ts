"use client";

import type { ThreadAssistantMessagePart, ThreadMessage } from "@assistant-ui/react";

type PhaseStartDataPart = {
  type: "data";
  name: "phase-start";
  data: { traceId?: string };
};

function isPhaseStartPart(
  part: ThreadAssistantMessagePart,
): part is PhaseStartDataPart {
  return part.type === "data" && "name" in part && part.name === "phase-start";
}

export function extractTraceId(message: ThreadMessage): string | null {
  if (message.role !== "assistant") return null;
  for (const part of message.content) {
    if (!isPhaseStartPart(part)) continue;
    const traceId = part.data.traceId;
    if (typeof traceId === "string" && traceId.length > 0) return traceId;
  }
  return null;
}
