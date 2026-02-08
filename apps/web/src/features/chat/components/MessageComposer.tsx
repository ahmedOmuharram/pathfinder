"use client";

import { useState, useRef, useEffect } from "react";
import { Square } from "lucide-react";
import type { ChatMode } from "@pathfinder/shared";

interface MessageComposerProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  mode?: ChatMode;
  isStreaming?: boolean;
  onStop?: () => void;
}

export function MessageComposer({
  onSend,
  disabled,
  mode = "execute",
  isStreaming = false,
  onStop,
}: MessageComposerProps) {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Allow external prefill (e.g. from planning mode "Build in executor").
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ message?: string; mode?: ChatMode }>)
        .detail;
      if (!detail || typeof detail.message !== "string") return;
      if (detail.mode && detail.mode !== mode) return;
      setMessage(detail.message);
      // Focus after state update (best-effort).
      setTimeout(() => textareaRef.current?.focus(), 0);
    };
    window.addEventListener("pathfinder:prefill-composer", handler);
    return () => window.removeEventListener("pathfinder:prefill-composer", handler);
  }, [mode]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [message]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !disabled) {
      onSend(message.trim());
      setMessage("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-end gap-2"
      data-testid="message-composer"
    >
      <textarea
        ref={textareaRef}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        data-testid="message-input"
        placeholder={
          mode === "plan"
            ? "Plan a strategy: goals, constraints, and evidence to include..."
            : "Ask me to build a search strategy..."
        }
        rows={1}
        className="min-w-0 flex-1 resize-none overflow-hidden rounded-md border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-900 placeholder-slate-400 focus:border-slate-300 focus:outline-none focus:ring-1 focus:ring-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
      />
      {isStreaming && onStop ? (
        <button
          type="button"
          onClick={onStop}
          data-testid="stop-button"
          className="shrink-0 rounded-md border border-slate-200 bg-white p-2 text-slate-700 transition-colors hover:bg-slate-50"
          aria-label="Stop"
          title="Stop"
        >
          <Square className="h-4 w-4" aria-hidden="true" />
        </button>
      ) : (
        <button
          type="submit"
          disabled={disabled || !message.trim()}
          data-testid="send-button"
          className="shrink-0 rounded-md border border-slate-200 bg-slate-900 p-2 text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Send"
          title="Send"
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
        </button>
      )}
    </form>
  );
}
