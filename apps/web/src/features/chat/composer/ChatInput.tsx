"use client";

import { useRef, useState, type KeyboardEvent } from "react";

import {
  PromptInput,
  PromptInputBody,
  PromptInputSubmit,
  PromptInputTextarea,
  type PromptInputMessage,
} from "@/components/ai-elements/prompt-input";

import { MentionDropdown } from "./MentionDropdown";
import {
  formatMentionToken,
  useMentionSuggestions,
} from "./useMentionSuggestions";

interface ChatInputProps {
  onSubmit: (text: string) => void;
  onStop: () => void;
  disabled: boolean;
}

interface MentionState {
  startIndex: number;
  query: string;
  activeIndex: number;
}

export function ChatInput({ onSubmit, onStop, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const [mention, setMention] = useState<MentionState | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const candidates = useMentionSuggestions(mention?.query ?? "");
  const canSubmit = text.trim().length > 0;
  const status = disabled ? "streaming" : "ready";

  const closeMention = (): void => {
    if (mention !== null) setMention(null);
  };

  const insertCandidate = (index: number): void => {
    if (mention === null) return;
    const candidate = candidates[index];
    if (candidate === undefined) return;
    const el = textareaRef.current;
    const token = `${formatMentionToken(candidate)} `;
    const cursor = el?.selectionStart ?? text.length;
    const before = text.slice(0, mention.startIndex);
    const after = text.slice(cursor);
    const next = `${before}${token}${after}`;
    setText(next);
    setMention(null);
    const nextCursor = mention.startIndex + token.length;
    window.requestAnimationFrame(() => {
      el?.setSelectionRange(nextCursor, nextCursor);
      el?.focus();
    });
  };

  const handleTextChange = (value: string, cursor: number): void => {
    setText(value);
    if (mention === null) return;
    const startIndex = mention.startIndex;
    if (cursor <= startIndex || value[startIndex] !== "@") {
      setMention(null);
      return;
    }
    const nextQuery = value.slice(startIndex + 1, cursor);
    if (nextQuery.includes(" ") || nextQuery.includes("\n")) {
      setMention(null);
      return;
    }
    setMention({ startIndex, query: nextQuery, activeIndex: 0 });
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (mention !== null && candidates.length > 0) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setMention({
          ...mention,
          activeIndex: (mention.activeIndex + 1) % candidates.length,
        });
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setMention({
          ...mention,
          activeIndex:
            (mention.activeIndex - 1 + candidates.length) % candidates.length,
        });
        return;
      }
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        insertCandidate(mention.activeIndex);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        closeMention();
        return;
      }
    }

    if (event.key === "@" && !disabled) {
      const cursor = event.currentTarget.selectionStart;
      const charBefore = cursor > 0 ? text[cursor - 1] : undefined;
      const isAtBoundary =
        charBefore === undefined || charBefore === " " || charBefore === "\n";
      if (isAtBoundary) {
        setMention({ startIndex: cursor, query: "", activeIndex: 0 });
      }
    }
  };

  const handlePromptSubmit = (message: PromptInputMessage): void => {
    if (message.text.trim().length > 0) {
      onSubmit(message.text);
      setText("");
      setMention(null);
    }
  };

  return (
    <div className="relative">
      {mention !== null && candidates.length > 0 ? (
        <MentionDropdown
          candidates={candidates}
          activeIndex={mention.activeIndex}
          onSelect={(candidate) => {
            const idx = candidates.indexOf(candidate);
            insertCandidate(idx);
          }}
        />
      ) : null}
      <PromptInput onSubmit={handlePromptSubmit}>
        <PromptInputBody>
          <PromptInputTextarea
            ref={textareaRef}
            value={text}
            onChange={(event) => {
              handleTextChange(event.target.value, event.target.selectionStart);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything… @ to reference a step or gene set"
            data-mention-open={
              mention !== null && candidates.length > 0 ? true : undefined
            }
          />
          <PromptInputSubmit
            status={status}
            onStop={onStop}
            disabled={!canSubmit && !disabled}
          />
        </PromptInputBody>
      </PromptInput>
    </div>
  );
}
