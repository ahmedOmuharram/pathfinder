"use client";

import { useState } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { cn } from "@/lib/utils/cn";
import { submitFeedback } from "@/lib/api/feedback";

interface MessageFeedbackProps {
  traceId: string | null;
  streamId: string;
}

type FeedbackState = "none" | "positive" | "negative";

export function MessageFeedback({ traceId, streamId }: MessageFeedbackProps) {
  const [state, setState] = useState<FeedbackState>("none");

  const handlePositive = () => {
    if (traceId == null || traceId === "") return;
    setState("positive");
    submitFeedback({ traceId, streamId, value: 1 }).catch(() => {
      setState("none");
    });
  };

  const handleNegative = () => {
    if (traceId == null || traceId === "") return;
    setState("negative");
    submitFeedback({ traceId, streamId, value: 0 }).catch(() => {
      setState("none");
    });
  };

  if (traceId == null || traceId === "") return null;

  return (
    <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
      <button
        type="button"
        onClick={handlePositive}
        disabled={state !== "none"}
        className={cn(
          "rounded p-1 transition-colors hover:bg-green-100 dark:hover:bg-green-900/30",
          state === "positive" && "bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400",
        )}
        aria-label="Helpful response"
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        onClick={handleNegative}
        disabled={state !== "none"}
        className={cn(
          "rounded p-1 transition-colors hover:bg-red-100 dark:hover:bg-red-900/30",
          state === "negative" && "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400",
        )}
        aria-label="Unhelpful response"
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
