"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { FileText, FlaskConical, Square, X } from "lucide-react";
import type {
  ChatMention,
  ChatMode,
  ModelCatalogEntry,
  ModelSelection,
  ReasoningEffort,
} from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";
import { ModelPicker } from "./ModelPicker";
import { ReasoningToggle } from "./ReasoningToggle";
import { MentionAutocomplete } from "./MentionAutocomplete";

interface MessageComposerProps {
  onSend: (message: string, mentions?: ChatMention[]) => void;
  disabled?: boolean;
  /** Current mode — used for composer prefill matching (plan vs execute). */
  mode?: ChatMode;
  isStreaming?: boolean;
  onStop?: () => void;
  /** Available models from the catalog. */
  models?: ModelCatalogEntry[];
  /** Currently selected model ID (null = server default). */
  selectedModelId?: string | null;
  onModelChange?: (modelId: string | null) => void;
  /** Current reasoning effort. */
  reasoningEffort?: ReasoningEffort;
  onReasoningChange?: (effort: ReasoningEffort) => void;
  /** Server default model ID for the current mode — shown in the picker. */
  serverDefaultModelId?: string | null;
  /** Site ID for @-mention data fetching. */
  siteId: string;
}

export function MessageComposer({
  onSend,
  disabled,
  mode = "execute",
  isStreaming = false,
  onStop,
  models = [],
  selectedModelId = null,
  onModelChange,
  reasoningEffort = "medium",
  onReasoningChange,
  serverDefaultModelId,
  siteId,
}: MessageComposerProps) {
  const [message, setMessage] = useState("");
  const [mentions, setMentions] = useState<ChatMention[]>([]);
  const [mentionActive, setMentionActive] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionPos, setMentionPos] = useState({ top: 0, left: 0 });
  const mentionStartRef = useRef<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Allow external prefill (e.g. from planning mode "Build in executor").
  const composerPrefill = useSessionStore((s) => s.composerPrefill);
  const setComposerPrefill = useSessionStore((s) => s.setComposerPrefill);
  useEffect(() => {
    if (!composerPrefill) return;
    if (composerPrefill.mode !== mode) return;
    const apply = () => {
      setMessage(composerPrefill.message);
      setComposerPrefill(null);
      setTimeout(() => textareaRef.current?.focus(), 0);
    };
    apply();
  }, [composerPrefill, mode, setComposerPrefill]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [message]);

  // Resolve whether selected model supports reasoning.
  // When using server default (selectedModelId null), use serverDefaultModelId to look up the model.
  const effectiveModelId = selectedModelId ?? serverDefaultModelId ?? null;
  const selectedModel = models.find((m) => m.id === effectiveModelId);
  const supportsReasoning = selectedModel?.supportsReasoning ?? false;

  const checkMentionTrigger = useCallback((value: string, cursorPos: number) => {
    const before = value.slice(0, cursorPos);
    const atIdx = before.lastIndexOf("@");
    if (
      atIdx === -1 ||
      (atIdx > 0 && before[atIdx - 1] !== " " && before[atIdx - 1] !== "\n")
    ) {
      setMentionActive(false);
      return;
    }
    const query = before.slice(atIdx + 1);
    if (query.includes(" ") && query.length > 20) {
      setMentionActive(false);
      return;
    }
    mentionStartRef.current = atIdx;
    setMentionQuery(query);
    setMentionPos({ top: 36, left: 8 });
    setMentionActive(true);
  }, []);

  const handleMentionSelect = useCallback(
    (mention: ChatMention) => {
      const start = mentionStartRef.current ?? 0;
      const before = message.slice(0, start);
      const textarea = textareaRef.current;
      const cursorPos = textarea?.selectionStart ?? message.length;
      const after = message.slice(cursorPos);
      setMessage(before + after);
      setMentions((prev) => {
        if (prev.some((m) => m.type === mention.type && m.id === mention.id))
          return prev;
        return [...prev, mention];
      });
      setMentionActive(false);
      setTimeout(() => textareaRef.current?.focus(), 0);
    },
    [message],
  );

  const removeMention = useCallback((idx: number) => {
    setMentions((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (mentionActive) return;
      if (message.trim() && !disabled) {
        onSend(message.trim(), mentions.length > 0 ? mentions : undefined);
        setMessage("");
        setMentions([]);
      }
    },
    [message, disabled, onSend, mentions, mentionActive],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (mentionActive) return;
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e);
      }
    },
    [handleSubmit, mentionActive],
  );

  return (
    <div className="flex flex-col gap-2" data-testid="message-composer">
      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Model picker */}
        {models.length > 0 && onModelChange && (
          <ModelPicker
            models={models}
            selectedModelId={selectedModelId}
            onSelect={(id) => onModelChange(id || null)}
            disabled={isStreaming}
            serverDefaultId={serverDefaultModelId}
          />
        )}

        {/* Reasoning effort toggle */}
        {supportsReasoning && onReasoningChange && (
          <ReasoningToggle
            value={reasoningEffort}
            onChange={onReasoningChange}
            disabled={isStreaming}
          />
        )}
      </div>

      {/* Input row */}
      <form onSubmit={handleSubmit} className="relative flex items-end gap-2">
        <MentionAutocomplete
          siteId={siteId}
          query={mentionQuery}
          position={mentionPos}
          visible={mentionActive}
          onSelect={handleMentionSelect}
          onDismiss={() => setMentionActive(false)}
        />
        <div className="min-w-0 flex-1 rounded-md border border-slate-200 bg-white focus-within:border-slate-300 focus-within:ring-1 focus-within:ring-slate-200">
          {/* Mention chips inside the input container */}
          {mentions.length > 0 && (
            <div className="flex flex-wrap gap-1.5 border-b border-slate-100 px-2.5 py-1.5">
              {mentions.map((m, i) => {
                const MIcon = m.type === "strategy" ? FileText : FlaskConical;
                return (
                  <span
                    key={`${m.type}-${m.id}`}
                    className="inline-flex items-center gap-1 rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 ring-1 ring-inset ring-blue-200"
                  >
                    <MIcon className="h-3 w-3 shrink-0" />
                    {m.displayName}
                    <button
                      type="button"
                      onClick={() => removeMention(i)}
                      className="ml-0.5 rounded p-0.5 text-blue-400 transition hover:bg-blue-100 hover:text-blue-600"
                    >
                      <X className="h-2.5 w-2.5" />
                    </button>
                  </span>
                );
              })}
            </div>
          )}
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
              checkMentionTrigger(e.target.value, e.target.selectionStart ?? 0);
            }}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            data-testid="message-input"
            placeholder={
              mentions.length > 0
                ? "Ask about referenced items..."
                : "Ask a question... Use @ to reference strategies or experiments"
            }
            rows={1}
            className="min-w-0 w-full resize-none overflow-hidden border-0 bg-transparent px-3 py-2 text-[13px] text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-0 disabled:cursor-not-allowed disabled:opacity-50"
          />
        </div>
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
    </div>
  );
}

/**
 * Derive a ModelSelection object from the current composer state.
 * Returns undefined if using server defaults.
 */
export function buildModelSelection(
  selectedModelId: string | null,
  reasoningEffort: ReasoningEffort,
  models: ModelCatalogEntry[],
): ModelSelection | undefined {
  if (!selectedModelId) return undefined;
  const entry = models.find((m) => m.id === selectedModelId);
  if (!entry) return undefined;
  return {
    provider: entry.provider,
    model: entry.id,
    reasoningEffort: entry.supportsReasoning ? reasoningEffort : undefined,
  };
}
