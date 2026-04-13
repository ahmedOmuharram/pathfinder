"use client";

/**
 * Rich message bubble.
 *
 * Reads from AI SDK v6 fields only — `message.role`, `message.metadata`,
 * `message.id`, `message.createdAt`. Assistant bubbles display an avatar +
 * provider label (derived from `metadata.model`), a phase tag, a timestamp,
 * and a footer with regenerate + thumbs up/down feedback. User bubbles are
 * compact and right-aligned. System bubbles are a dashed hint.
 *
 * Regenerate calls `useChat().regenerate()` via the chat session context.
 * Feedback POSTs to `/api/v1/feedback` keyed by `metadata.traceId` (backend
 * endpoint already exists, routes to Langfuse).
 *
 * This component is the visual wrapper; message parts flow inside as
 * children — tool calls, text, reasoning, etc. render in order (Claude-style
 * inline chronological — see docs/superpowers/chat-overhaul/04-decisions.md
 * §Decision 7).
 */

import { Bot, Sparkles, User, type LucideIcon } from "lucide-react";
import { type ReactNode } from "react";

import type {
  CompletedAssistantMetadata,
  PathfinderMessageMetadata,
  PathfinderUIMessage,
} from "@pathfinder/shared";

import { buildCitationIndex } from "./citations/buildIndex";
import { CitationsProvider } from "./citations/CitationsContext";
import { SourcesFooter } from "./citations/SourcesFooter";
import { AssistantFooter } from "./MessageFooter";

/**
 * Fails loud when a completed assistant message is missing required metadata.
 *
 * During streaming, `MessageMetadataChunk`s arrive at different times so
 * partial metadata is expected. Once the stream ends (`isComplete` true),
 * `phase` / `model` / `traceId` / `createdAt` must all be present. Missing
 * fields at completion time are a backend bug — we surface it here instead
 * of silently rendering blank avatars or timestamps.
 */
function assertCompletedAssistantMetadata(
  meta: PathfinderMessageMetadata | undefined,
  messageId: string,
): asserts meta is CompletedAssistantMetadata {
  const missing: string[] = [];
  if (meta === undefined) {
    throw new Error(
      `assistant message ${messageId} is complete but has no metadata; backend did not emit any MessageMetadataChunk`,
    );
  }
  if (meta.phase === undefined) missing.push("phase");
  if (meta.model === undefined) missing.push("model");
  if (meta.traceId === undefined) missing.push("traceId");
  if (meta.createdAt === undefined) missing.push("createdAt");
  if (missing.length > 0) {
    throw new Error(
      `assistant message ${messageId} is complete but missing required metadata: ${missing.join(", ")}`,
    );
  }
}

const ROLE_STYLES: Record<"user" | "assistant" | "system", string> = {
  user: "ml-auto max-w-[80%] rounded-lg bg-primary px-3 py-2 text-primary-foreground",
  assistant:
    "mr-auto w-full max-w-full rounded-lg border border-border bg-card px-3 py-2 text-foreground",
  system:
    "mx-auto max-w-[90%] rounded border border-dashed border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground",
};

export function MessageBubble({
  message,
  isLatest,
  isComplete,
  children,
}: {
  message: PathfinderUIMessage;
  isLatest: boolean;
  /**
   * Whether streaming has finished for this message. When `true` on an
   * assistant message, metadata MUST be fully populated — the type guard
   * throws otherwise. When `false`, partial metadata is rendered as-is
   * (streaming reality: chunks arrive incrementally).
   */
  isComplete: boolean;
  children: ReactNode;
}) {
  const { role, metadata, id, parts } = message;
  const isAssistant = role === "assistant";
  const isSystem = role === "system";
  const citations = buildCitationIndex(parts);

  if (isAssistant && isComplete) {
    assertCompletedAssistantMetadata(metadata, id);
  }
  const phaseLabel = metadata?.phase;

  return (
    <div
      data-testid="message-bubble"
      data-role={role}
      data-phase={phaseLabel ?? undefined}
      data-latest={isLatest || undefined}
      data-complete={isComplete || undefined}
      className={`my-2 flex gap-2 ${isAssistant ? "flex-row" : "flex-row-reverse"}`}
    >
      {!isSystem && <Avatar role={role} modelId={metadata?.model} />}

      <div className={`flex min-w-0 flex-1 flex-col ${ROLE_STYLES[role]}`}>
        {isAssistant && isComplete ? (
          <AssistantHeaderCompleted metadata={metadata as CompletedAssistantMetadata} />
        ) : isAssistant ? (
          <AssistantHeaderStreaming metadata={metadata ?? {}} />
        ) : null}
        <CitationsProvider index={citations}>
          <div className="space-y-2">{children}</div>
        </CitationsProvider>
        {isAssistant && citations.entries.length > 0 && (
          <SourcesFooter entries={citations.entries} />
        )}
        {isAssistant && isComplete && (
          <AssistantFooter
            messageId={id}
            traceId={(metadata as CompletedAssistantMetadata).traceId}
            isLatest={isLatest}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Small avatar tile — uses lucide icons and a subtle tint per role.
 * The model badge (if any) renders as a tooltip-like label below.
 */
function Avatar({
  role,
  modelId,
}: {
  role: "user" | "assistant" | "system";
  modelId: string | undefined;
}) {
  const { Icon, tint } = iconForRole(role, modelId);
  return (
    <div
      className={`mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${tint}`}
      aria-hidden="true"
      data-testid="message-avatar"
      data-role={role}
    >
      <Icon className="h-3.5 w-3.5" />
    </div>
  );
}

function iconForRole(
  role: "user" | "assistant" | "system",
  modelId: string | undefined,
): { Icon: LucideIcon; tint: string } {
  if (role === "user") {
    return { Icon: User, tint: "bg-primary/10 text-primary" };
  }
  if (role === "assistant") {
    const provider = (modelId ?? "").toLowerCase();
    if (provider.includes("claude") || provider.includes("anthropic")) {
      return { Icon: Sparkles, tint: "bg-orange-500/10 text-orange-500" };
    }
    if (provider.includes("gpt") || provider.includes("openai")) {
      return { Icon: Bot, tint: "bg-emerald-500/10 text-emerald-500" };
    }
    return { Icon: Bot, tint: "bg-muted text-muted-foreground" };
  }
  return { Icon: Bot, tint: "bg-muted text-muted-foreground" };
}

/**
 * Header for a fully-streamed assistant message — metadata is guaranteed
 * complete by the caller (`assertCompletedAssistantMetadata` ran upstream).
 * No null checks, no fallbacks: every field renders.
 */
function AssistantHeaderCompleted({
  metadata,
}: {
  metadata: CompletedAssistantMetadata;
}) {
  const modelLabel = shortenModelId(metadata.model);
  const timestamp = formatTimestamp(metadata.createdAt);
  return (
    <div
      className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground"
      data-testid="message-header"
    >
      <span className="font-medium text-foreground/70" data-testid="message-model">
        {modelLabel}
      </span>
      {metadata.phase !== "completed" && (
        <span
          className="rounded border border-border/60 bg-accent/40 px-1.5 py-0.5 text-accent-foreground"
          data-testid="message-phase"
        >
          {metadata.phase}
        </span>
      )}
      <span className="ml-auto" data-testid="message-time">
        {timestamp}
      </span>
    </div>
  );
}

/**
 * Header for an assistant message whose stream hasn't completed yet. Metadata
 * chunks arrive incrementally — any of model/phase/timestamp may still be
 * missing. Renders what we have and suppresses the bar entirely if nothing
 * has arrived.
 */
function AssistantHeaderStreaming({
  metadata,
}: {
  metadata: PathfinderMessageMetadata;
}) {
  const modelLabel = shortenModelId(metadata.model);
  const phaseLabel = metadata.phase;
  const timestamp = formatTimestamp(metadata.createdAt);
  if (modelLabel === undefined && phaseLabel === undefined && timestamp === undefined) {
    return null;
  }
  return (
    <div
      className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground"
      data-testid="message-header"
    >
      {modelLabel !== undefined && (
        <span className="font-medium text-foreground/70" data-testid="message-model">
          {modelLabel}
        </span>
      )}
      {phaseLabel !== undefined && phaseLabel !== "completed" && (
        <span
          className="rounded border border-border/60 bg-accent/40 px-1.5 py-0.5 text-accent-foreground"
          data-testid="message-phase"
        >
          {phaseLabel}
        </span>
      )}
      {timestamp !== undefined && (
        <span className="ml-auto" data-testid="message-time">
          {timestamp}
        </span>
      )}
    </div>
  );
}

function shortenModelId(modelId: string | undefined): string | undefined {
  if (modelId === undefined || modelId.length === 0) return undefined;
  const tail = modelId.split("/").at(-1) ?? modelId;
  return tail;
}

function formatTimestamp(iso: string | undefined): string | undefined {
  if (iso === undefined || iso.length === 0) return undefined;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return undefined;
  try {
    return new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  } catch {
    return undefined;
  }
}
