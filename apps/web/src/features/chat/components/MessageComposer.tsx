"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Square, FileText } from "lucide-react";
import type {
  ChatMode,
  ModelCatalogEntry,
  ModelSelection,
  ReasoningEffort,
} from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";
import { ModelPicker } from "./ModelPicker";
import { ReasoningToggle } from "./ReasoningToggle";

interface MessageComposerProps {
  onSend: (message: string) => void;
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
  /** Callback to open insert-strategy modal (shown when no strategy is attached). */
  onInsertStrategy?: () => void;
  /** Server default model ID for the current mode — shown in the picker. */
  serverDefaultModelId?: string | null;
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
  onInsertStrategy,
  serverDefaultModelId,
}: MessageComposerProps) {
  const [message, setMessage] = useState("");
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

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (message.trim() && !disabled) {
        onSend(message.trim());
        setMessage("");
      }
    },
    [message, disabled, onSend],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e);
      }
    },
    [handleSubmit],
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

        {/* Reference strategy button (visible when no strategy is attached / plan mode) */}
        {onInsertStrategy && (
          <button
            type="button"
            onClick={onInsertStrategy}
            disabled={isStreaming}
            className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <FileText className="h-3 w-3" aria-hidden />
            Reference a Strategy
          </button>
        )}
      </div>

      {/* Input row */}
      <form onSubmit={handleSubmit} className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          data-testid="message-input"
          placeholder="Ask me to build a search strategy or describe your research question..."
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
