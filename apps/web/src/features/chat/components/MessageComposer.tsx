"use client";

import { useState, useRef } from "react";
import { Square } from "lucide-react";
import type { ChatMention } from "@pathfinder/shared";
import { useShallow } from "zustand/react/shallow";
import { useSessionStore } from "@/state/useSessionStore";
import { Button } from "@/lib/components/ui/Button";


import { PipelinePill } from "@/features/engine/components/PipelinePill";
import { useMentionState } from "@/features/chat/hooks/useMentionState";
import { MentionBadges } from "./message/MentionBadges";
import { MentionAutocomplete } from "./message/MentionAutocomplete";

interface MessageComposerProps {
  onSend: (message: string, mentions?: ChatMention[]) => void;
  disabled?: boolean;
  isStreaming?: boolean;
  onStop?: () => void;
  onOpenEngine?: (() => void) | undefined;
  /** Site ID for @-mention data fetching. */
  siteId: string;
}

export function MessageComposer({
  onSend,
  disabled,
  isStreaming = false,
  onStop,
  onOpenEngine,
  siteId,
}: MessageComposerProps) {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
    mentions,
    setMentions,
    mentionActive,
    setMentionActive,
    mentionQuery,
    mentionPos,
    checkMentionTrigger,
    handleMentionSelect,
    removeMention,
  } = useMentionState();

  // Allow external prefill (e.g. from graph node "Ask about" action).
  const { composerPrefill, setComposerPrefill } = useSessionStore(
    useShallow((s) => ({
      composerPrefill: s.composerPrefill,
      setComposerPrefill: s.setComposerPrefill,
    })),
  );
  const [consumedPrefill, setConsumedPrefill] = useState<string | null>(null);
  if (composerPrefill && composerPrefill.message !== consumedPrefill) {
    setConsumedPrefill(composerPrefill.message);
    setMessage(composerPrefill.message);
    setComposerPrefill(null);
  }

  const onMentionSelect = (mention: ChatMention) => {
    handleMentionSelect(mention, message, textareaRef, setMessage);
  };

  const handleSubmit = (e: { preventDefault: () => void }) => {
    e.preventDefault();
    if (mentionActive === true) return;
    if (message.trim() !== "" && disabled !== true) {
      onSend(message.trim(), mentions.length > 0 ? mentions : undefined);
      setMessage("");
      setMentions([]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (mentionActive === true) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="flex flex-col gap-2" data-testid="message-composer">
      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Pipeline pill — opens Engine Modal */}
        <PipelinePill onClick={onOpenEngine ?? (() => {})} />

      </div>

      {/* Input row */}
      <form onSubmit={handleSubmit} className="relative flex items-end gap-2">
        <MentionAutocomplete
          siteId={siteId}
          query={mentionQuery}
          position={mentionPos}
          visible={mentionActive}
          onSelect={onMentionSelect}
          onDismiss={() => setMentionActive(false)}
        />
        <div className="min-w-0 flex-1 rounded-md border border-input bg-background transition-colors duration-150 focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/20">
          <MentionBadges mentions={mentions} onRemove={removeMention} />
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
              checkMentionTrigger(e.target.value, e.target.selectionStart);
            }}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            data-testid="message-input"
            placeholder={
              mentions.length > 0
                ? "Continue with referenced items..."
                : "Describe a research goal, or @ to reference a strategy"
            }
            rows={1}
            className="min-w-0 w-full max-h-[200px] resize-none overflow-auto border-0 bg-transparent px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-0 disabled:cursor-not-allowed disabled:opacity-50 [field-sizing:content]"
          />
        </div>
        {isStreaming && onStop ? (
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={onStop}
            data-testid="stop-button"
            aria-label="Stop"
          >
            <Square className="h-4 w-4" aria-hidden="true" />
          </Button>
        ) : (
          <Button
            type="submit"
            size="icon"
            disabled={disabled === true || message.trim() === ""}
            data-testid="send-button"
            aria-label="Send"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              className="h-4 w-4"
            >
              <path d="M22 2L11 13" />
              <path d="M22 2L15 22L11 13L2 9L22 2Z" />
            </svg>
          </Button>
        )}
      </form>
    </div>
  );
}

