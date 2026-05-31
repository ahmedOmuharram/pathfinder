"use client";

import type { FeedbackAdapter } from "@assistant-ui/react";
import { toast } from "sonner";

import { requestVoid } from "@/lib/api/http";

import { extractTraceId } from "./traceId";

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
            type === "positive"
              ? "Thanks for the feedback"
              : "Thanks — we'll learn from this",
          );
        } catch (err) {
          toast.error(err instanceof Error ? err.message : "Failed to submit feedback");
        }
      })();
    },
  };
}
