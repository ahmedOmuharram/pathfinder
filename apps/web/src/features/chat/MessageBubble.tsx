"use client";

import { Bot, Sparkles, User, type LucideIcon } from "lucide-react";
import { type ReactNode } from "react";

import type {
  CompletedAssistantMetadata,
  PathfinderMessageMetadata,
  PathfinderUIMessage,
} from "@pathfinder/shared";

import {
  Context,
  ContextContent,
  ContextContentBody,
  ContextContentFooter,
  ContextContentHeader,
  ContextTrigger,
} from "@/components/ai-elements/context";
import { Message, MessageContent } from "@/components/ai-elements/message";

import { buildCitationIndex } from "./citations/buildIndex";
import { CitationsProvider } from "./citations/CitationsContext";
import { SourcesFooter } from "./citations/SourcesFooter";
import { AssistantFooter } from "./MessageFooter";

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

export function MessageBubble({
  message,
  isLatest,
  isComplete,
  children,
}: {
  message: PathfinderUIMessage;
  isLatest: boolean;
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

  if (isSystem) {
    return (
      <Message
        from={role}
        data-testid="message-bubble"
        data-role={role}
        data-latest={isLatest || undefined}
        data-complete={isComplete || undefined}
      >
        <MessageContent className="mx-auto max-w-[90%] rounded border border-dashed border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
          {children}
        </MessageContent>
      </Message>
    );
  }

  return (
    <Message
      from={role}
      data-testid="message-bubble"
      data-role={role}
      data-phase={phaseLabel ?? undefined}
      data-latest={isLatest || undefined}
      data-complete={isComplete || undefined}
      className={`my-2 flex w-full max-w-full flex-row gap-2 ${isAssistant ? "" : "flex-row-reverse"}`}
    >
      <Avatar role={role} modelId={metadata?.model} />
      <MessageContent className="min-w-0 flex-1">
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
      </MessageContent>
    </Message>
  );
}

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
      <ContextUsage
        used={metadata.tokensUsed}
        budget={metadata.tokensBudget}
        modelId={metadata.model}
      />
      <span className="ml-auto" data-testid="message-time">
        {timestamp}
      </span>
    </div>
  );
}

function ContextUsage({
  used,
  budget,
  modelId,
}: {
  used: number | undefined;
  budget: number | undefined;
  modelId: string | undefined;
}) {
  if (used === undefined || budget === undefined || budget === 0) return null;
  return (
    <Context
      usedTokens={used}
      maxTokens={budget}
      {...(modelId !== undefined ? { modelId } : {})}
    >
      <ContextTrigger className="h-5 px-1 py-0 text-[10px]" data-testid="message-context" />
      <ContextContent>
        <ContextContentHeader />
        <ContextContentBody />
        <ContextContentFooter />
      </ContextContent>
    </Context>
  );
}

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
