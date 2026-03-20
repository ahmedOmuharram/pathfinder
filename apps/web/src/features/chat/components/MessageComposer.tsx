"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Square } from "lucide-react";
import type {
  ChatMention,
  ModelCatalogEntry,
  ModelSelection,
  ReasoningEffort,
} from "@pathfinder/shared";
import { useSessionStore } from "@/state/useSessionStore";
import type { ModelOverrides } from "@/state/useSettingsStore";
import { Button } from "@/lib/components/ui/Button";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/lib/components/ui/Tooltip";
import { ModelPicker } from "@/lib/components/ModelPicker";
import { ReasoningToggle } from "@/lib/components/ReasoningToggle";
import { ToolPicker } from "@/lib/components/ToolPicker";
import { useMentionState } from "@/features/chat/hooks/useMentionState";
import { MentionBadges } from "./message/MentionBadges";
import { MentionAutocomplete } from "./message/MentionAutocomplete";

interface MessageComposerProps {
  onSend: (message: string, mentions?: ChatMention[]) => void;
  disabled?: boolean;
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
  /** Server default model ID for the current mode -- shown in the picker. */
  serverDefaultModelId?: string | null;
  /** Site ID for @-mention data fetching. */
  siteId: string;
}

export function MessageComposer({
  onSend,
  disabled,
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
  const composerPrefill = useSessionStore((s) => s.composerPrefill);
  const setComposerPrefill = useSessionStore((s) => s.setComposerPrefill);
  useEffect(() => {
    if (!composerPrefill) return;
    // Defer the state update to avoid synchronous setState in effect body.
    const id = requestAnimationFrame(() => {
      setMessage(composerPrefill.message);
      setComposerPrefill(null);
      textareaRef.current?.focus();
    });
    return () => cancelAnimationFrame(id);
  }, [composerPrefill, setComposerPrefill]);

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

  const onMentionSelect = useCallback(
    (mention: ChatMention) => {
      handleMentionSelect(mention, message, textareaRef, setMessage);
    },
    [handleMentionSelect, message],
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (mentionActive === true) return;
      if (message.trim() !== "" && disabled !== true) {
        onSend(message.trim(), mentions.length > 0 ? mentions : undefined);
        setMessage("");
        setMentions([]);
      }
    },
    [message, disabled, onSend, mentions, mentionActive, setMentions],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (mentionActive === true) return;
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
          <Tooltip>
            <TooltipTrigger asChild>
              <div>
                <ModelPicker
                  models={models}
                  selectedModelId={selectedModelId}
                  onSelect={(id) => onModelChange(id ?? null)}
                  disabled={isStreaming}
                  {...(serverDefaultModelId != null
                    ? { serverDefaultId: serverDefaultModelId }
                    : {})}
                />
              </div>
            </TooltipTrigger>
            <TooltipContent>Choose the AI model for this message</TooltipContent>
          </Tooltip>
        )}

        {/* Tool picker */}
        <Tooltip>
          <TooltipTrigger asChild>
            <div>
              <ToolPicker disabled={isStreaming} />
            </div>
          </TooltipTrigger>
          <TooltipContent>Enable or disable AI tools</TooltipContent>
        </Tooltip>

        {/* Reasoning effort toggle */}
        {supportsReasoning && onReasoningChange && (
          <Tooltip>
            <TooltipTrigger asChild>
              <div>
                <ReasoningToggle
                  value={reasoningEffort}
                  onChange={onReasoningChange}
                  disabled={isStreaming}
                />
              </div>
            </TooltipTrigger>
            <TooltipContent>
              Higher effort produces more detailed analysis
            </TooltipContent>
          </Tooltip>
        )}
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
              checkMentionTrigger(e.target.value, e.target.selectionStart ?? 0);
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
            className="min-w-0 w-full resize-none overflow-hidden border-0 bg-transparent px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-0 disabled:cursor-not-allowed disabled:opacity-50"
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
            disabled={disabled || !message.trim()}
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

/**
 * Derive a ModelSelection object from the current composer state.
 * Returns undefined if using server defaults.
 */
export function buildModelSelection(
  selectedModelId: string | null,
  reasoningEffort: ReasoningEffort,
  models: ModelCatalogEntry[],
  overrides?: ModelOverrides,
): ModelSelection | undefined {
  if (selectedModelId === null || selectedModelId === "") return undefined;
  const entry = models.find((m) => m.id === selectedModelId);
  if (!entry) return undefined;
  return {
    provider: entry.provider,
    model: entry.id,
    ...(entry.supportsReasoning ? { reasoningEffort } : {}),
    ...(overrides?.contextSize != null ? { contextSize: overrides.contextSize } : {}),
    ...(overrides?.responseTokens != null
      ? { responseTokens: overrides.responseTokens }
      : {}),
    ...(overrides?.reasoningBudget != null
      ? { reasoningBudget: overrides.reasoningBudget }
      : {}),
  };
}
