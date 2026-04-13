"use client";

/**
 * Footer row for completed assistant bubbles: regenerate + thumbs up/down.
 *
 * Only rendered when the assistant message is complete — `traceId` is
 * guaranteed present at that point (see `assertCompletedAssistantMetadata`
 * in `MessageBubble`). Feedback POSTs to `/api/v1/feedback` (Langfuse sink);
 * regenerate calls native `useChat().regenerate()`.
 */

import { RefreshCcw, ThumbsDown, ThumbsUp } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";

import { useChatSessionContext } from "./approval/useChatContext";
import { submitFeedback } from "@/lib/api/feedback";

export function AssistantFooter({
  messageId,
  traceId,
  isLatest,
}: {
  messageId: string;
  traceId: string;
  isLatest: boolean;
}) {
  const { regenerate } = useChatSessionContext();
  const [submitted, setSubmitted] = useState<number | null>(null);

  const onRate = (value: number): void => {
    if (submitted !== null) return;
    setSubmitted(value);
    void submitFeedback({
      traceId,
      streamId: messageId,
      value,
    }).catch(() => {
      setSubmitted(null);
    });
  };

  return (
    <div
      className="mt-2 flex items-center gap-1 border-t border-border/40 pt-1.5 text-muted-foreground"
      data-testid="message-footer"
    >
      {isLatest && (
        <FooterButton
          label="Regenerate"
          icon={RefreshCcw}
          onClick={() => {
            void regenerate();
          }}
          testId="message-regenerate"
        />
      )}
      <FooterButton
        label="Helpful"
        icon={ThumbsUp}
        onClick={() => {
          onRate(1);
        }}
        disabled={submitted !== null}
        active={submitted === 1}
        testId="message-thumbs-up"
      />
      <FooterButton
        label="Not helpful"
        icon={ThumbsDown}
        onClick={() => {
          onRate(0);
        }}
        disabled={submitted !== null}
        active={submitted === 0}
        testId="message-thumbs-down"
      />
    </div>
  );
}

function FooterButton({
  label,
  icon: Icon,
  onClick,
  disabled,
  active,
  testId,
}: {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
  testId: string;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      data-testid={testId}
      data-active={active === true ? true : undefined}
      disabled={disabled}
      onClick={onClick}
      className={`inline-flex h-6 w-6 items-center justify-center rounded transition-colors hover:bg-accent hover:text-accent-foreground disabled:cursor-not-allowed disabled:opacity-40 ${
        active === true ? "bg-accent text-accent-foreground" : ""
      }`}
    >
      <Icon className="h-3 w-3" />
    </button>
  );
}
