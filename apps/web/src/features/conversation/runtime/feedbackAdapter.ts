"use client";

import type { FeedbackAdapter } from "@assistant-ui/react";
import type { ThreadAssistantMessagePart, ThreadMessage } from "@assistant-ui/react";
import { toast } from "sonner";

import { requestVoid } from "@/lib/api/http";

type PhaseStartDataPart = {
  type: "data";
  name: "phase-start";
  data: { traceId?: string };
};

function isPhaseStartPart(
  part: ThreadAssistantMessagePart,
): part is PhaseStartDataPart {
  return (
    part.type === "data"
    && "name" in part
    && part.name === "phase-start"
  );
}

function extractTraceId(message: ThreadMessage): string | null {
  if (message.role !== "assistant") return null;
  for (const part of message.content) {
    if (!isPhaseStartPart(part)) continue;
    const traceId = part.data.traceId;
    if (typeof traceId === "string" && traceId.length > 0) return traceId;
  }
  return null;
}

export function createFeedbackAdapter(): FeedbackAdapter {
  return {
    submit: ({ message, type }) => {
      const traceId = extractTraceId(message);
      if (traceId === null) {
        toast.error(
          "No trace id on this message yet — feedback can only be attached once the assistant has emitted a phase.",
        );
        return;
      }
      void (async () => {
        try {
          await requestVoid("/api/v1/feedback", {
            method: "POST",
            body: {
              traceId,
              streamId: message.id,
              value: type === "positive" ? 1 : 0,
            },
          });
          toast.success(
            type === "positive" ? "Thanks for the feedback" : "Thanks — we'll learn from this",
          );
        } catch (err) {
          toast.error(
            err instanceof Error ? err.message : "Failed to submit feedback",
          );
        }
      })();
    },
  };
}
