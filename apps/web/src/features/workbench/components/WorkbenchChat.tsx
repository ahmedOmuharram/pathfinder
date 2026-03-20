"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  MessageCircle,
  ChevronDown,
  ChevronUp,
  Send,
  Square,
  Loader2,
  Wrench,
} from "lucide-react";
import { ChatMarkdown } from "@/lib/components/ChatMarkdown";
import { Card } from "@/lib/components/ui/Card";
import { useWorkbenchChat, type WorkbenchMessage } from "../hooks/useWorkbenchChat";

interface WorkbenchChatProps {
  experimentId: string | null;
  siteId: string;
}

export function WorkbenchChat({ experimentId, siteId }: WorkbenchChatProps) {
  const [expanded, setExpanded] = useState(true);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const { messages, streaming, activeToolCalls, error, sendMessage, stop } =
    useWorkbenchChat(experimentId, siteId);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, activeToolCalls]);

  const handleSubmit = useCallback(
    (e?: { preventDefault: () => void }) => {
      e?.preventDefault();
      const text = input.trim();
      if (!text || streaming) return;
      setInput("");
      sendMessage(text);
    },
    [input, streaming, sendMessage],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  return (
    <Card>
      {/* Header */}
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left transition-colors hover:bg-accent/50"
      >
        <MessageCircle className="h-4 w-4 text-primary" />
        <span className="text-sm font-medium text-foreground">
          AI Research Assistant
        </span>
        {streaming && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            Thinking...
          </span>
        )}
        <span className="ml-auto">
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </span>
      </button>

      {/* Expandable body */}
      {expanded && (
        <div className="border-t">
          {/* Message history */}
          <div
            ref={scrollRef}
            className="max-h-[50vh] overflow-y-auto px-4 py-3 space-y-3"
          >
            {experimentId == null && messages.length === 0 && (
              <p className="py-4 text-center text-xs text-muted-foreground">
                Run an experiment to start chatting about your results.
              </p>
            )}

            {experimentId != null && messages.length === 0 && !streaming && (
              <p className="py-4 text-center text-xs text-muted-foreground">
                The AI assistant will automatically interpret your experiment results.
              </p>
            )}

            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {/* Active tool calls */}
            {activeToolCalls.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {activeToolCalls.map((tc) => (
                  <span
                    key={tc.id}
                    className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground"
                  >
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
                    </span>
                    {formatToolName(tc.name)}
                  </span>
                ))}
              </div>
            )}

            {/* Streaming indicator when no content yet */}
            {streaming &&
              messages.length > 0 &&
              activeToolCalls.length === 0 &&
              (() => {
                const last = messages[messages.length - 1];
                return last?.role === "user";
              })() && (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Thinking...
                </div>
              )}
          </div>

          {/* Error display */}
          {error != null && error !== "" && (
            <div className="text-sm text-red-500 px-3 py-1">{error}</div>
          )}

          {/* Input area */}
          <form
            onSubmit={handleSubmit}
            className="flex items-end gap-2 border-t px-4 py-2.5"
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                experimentId != null
                  ? "Ask about your results..."
                  : "Run an experiment first..."
              }
              disabled={experimentId == null || streaming}
              rows={1}
              className="min-h-[36px] max-h-[120px] flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
            />
            {streaming ? (
              <button
                type="button"
                onClick={stop}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-destructive text-destructive-foreground transition hover:bg-destructive/90"
                aria-label="Stop"
              >
                <Square className="h-3.5 w-3.5" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={experimentId == null || !input.trim()}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
                aria-label="Send"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            )}
          </form>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: WorkbenchMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {/* Completed tool calls */}
      {message.toolCalls && message.toolCalls.length > 0 && (
        <div className="space-y-1">
          {message.toolCalls.map((tc) => (
            <details key={tc.id} className="group">
              <summary className="inline-flex cursor-pointer items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted">
                <Wrench className="h-3 w-3" />
                {formatToolName(tc.name)}
                {tc.result != null && tc.result !== "" && (
                  <span className="text-green-600 dark:text-green-400">done</span>
                )}
              </summary>
              {tc.result != null && tc.result !== "" && (
                <pre className="mt-1 max-h-40 overflow-auto rounded bg-muted p-2 text-[10px] text-muted-foreground">
                  {tc.result}
                </pre>
              )}
            </details>
          ))}
        </div>
      )}

      {/* Assistant text */}
      {message.content && (
        <ChatMarkdown
          content={message.content}
          citations={message.citations ?? null}
          className="text-sm leading-relaxed text-foreground [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_p]:break-words [&_h1]:text-sm [&_h2]:text-sm [&_h3]:text-sm"
        />
      )}
    </div>
  );
}

function formatToolName(name: string): string {
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
