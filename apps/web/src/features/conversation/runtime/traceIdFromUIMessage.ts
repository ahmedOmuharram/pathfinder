"use client";

import type { UIMessage } from "ai";

export function extractTraceIdFromUIMessage(message: UIMessage): string | null {
  if (message.role !== "assistant") return null;
  for (const part of message.parts) {
    if (part.type !== "data-phase-start") continue;
    const data = (part as { data?: { traceId?: unknown } }).data;
    const traceId = data?.traceId;
    if (typeof traceId === "string" && traceId.length > 0) return traceId;
  }
  return null;
}
