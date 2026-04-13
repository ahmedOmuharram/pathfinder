"use client";

/**
 * Chat composer textarea with Send/Stop swap and @-mention completion.
 *
 * Owns the local draft text plus a lightweight mention-dropdown state machine:
 * when the user types `@` at a word boundary, we start tracking a query; keys
 * pressed while the dropdown is open extend or filter the query; arrow keys
 * navigate; Enter inserts the selected candidate as `@{kind}:{id}` at the
 * cursor; Escape or Space closes the dropdown.
 *
 * Mentions are plain text — no wire-format change. The agent receives the
 * inserted token via the normal `sendMessage({text})` path and resolves the
 * reference on its own (it can see the active strategy, steps, and gene sets
 * via its existing tools).
 *
 * Submitting while empty is a no-op. Shift+Enter always inserts a newline;
 * plain Enter submits unless the mention dropdown is open (in which case it
 * selects the active candidate).
 */

import { useRef, useState, type KeyboardEvent } from "react";

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
  /** Cursor index in `text` where the `@` sits. */
  startIndex: number;
  query: string;
  activeIndex: number;
}

export function ChatInput({ onSubmit, onStop, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const [mention, setMention] = useState<MentionState | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const canSubmit = text.trim().length > 0;
  const candidates = useMentionSuggestions(mention?.query ?? "");

  const submit = (): void => {
    if (!canSubmit) return;
    onSubmit(text);
    setText("");
    setMention(null);
  };

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
    // Defer cursor placement until after the state update has flushed so the
    // textarea DOM matches the new value.
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

    if (event.key === "Enter" && !event.shiftKey && !disabled) {
      event.preventDefault();
      submit();
      return;
    }

    if (event.key === "@" && !disabled) {
      const cursor = event.currentTarget.selectionStart;
      const charBefore = cursor > 0 ? text[cursor - 1] : undefined;
      const isAtBoundary =
        charBefore === undefined ||
        charBefore === " " ||
        charBefore === "\n";
      if (isAtBoundary) {
        setMention({ startIndex: cursor, query: "", activeIndex: 0 });
      }
    }
  };

  return (
    <form
      className="relative"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
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
      <div className="flex items-end gap-2 rounded-md border border-border bg-card p-1.5">
        <textarea
          ref={textareaRef}
          className="flex-1 resize-none bg-transparent px-1 py-1 text-sm outline-none placeholder:text-muted-foreground"
          value={text}
          onChange={(event) => {
            handleTextChange(event.target.value, event.target.selectionStart);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything… @ to reference a step or gene set"
          rows={2}
          data-mention-open={
            mention !== null && candidates.length > 0 ? true : undefined
          }
        />
        {disabled ? (
          <button
            type="button"
            onClick={onStop}
            className="rounded px-3 py-1 text-xs font-medium text-destructive hover:bg-destructive/10"
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            className="rounded bg-primary px-3 py-1 text-xs font-medium text-primary-foreground disabled:opacity-50"
            disabled={!canSubmit}
          >
            Send
          </button>
        )}
      </div>
    </form>
  );
}
