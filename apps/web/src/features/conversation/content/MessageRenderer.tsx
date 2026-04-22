"use client";

import {
  ActionBarPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  useMessage,
  type DataMessagePartComponent,
  type ReasoningMessagePartComponent,
  type TextMessagePartComponent,
  type ThreadMessage,
  type ToolCallMessagePartComponent,
} from "@assistant-ui/react";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";
import { Shimmer } from "@/components/ai-elements/shimmer";
import type { DataPartKind } from "@pathfinder/shared";
import type { ToolUIPart } from "ai";
import {
  AlertTriangle,
  Check,
  Copy,
  Pencil,
  RefreshCw,
  ThumbsDown,
  ThumbsUp,
  X,
} from "lucide-react";

import { BranchMessageAction } from "./BranchMessageAction";
import { EditComposerBranchOrRevert } from "./EditComposerSend";
import { motion } from "motion/react";
import { toast } from "sonner";

import {
  Message,
  MessageAction,
  MessageActions,
  MessageContent,
} from "@/components/ai-elements/message";
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import { Button } from "@/components/ui/button";

import { DataPartRenderer } from "./DataPartRenderer";
import { ModelBadge } from "./ModelBadge";
import { dataPartComponents } from "./contentComponents";
import { ToolThink } from "./parts/ToolThink";

const DATA_PREFIX = "data-" as const;

const markdownRemarkPlugins = [remarkGfm];

const Text: TextMessagePartComponent = () => (
  <MarkdownTextPrimitive
    remarkPlugins={markdownRemarkPlugins}
    className="prose prose-sm max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
  />
);

const ReasoningPart: ReasoningMessagePartComponent = ({ text, status }) => (
  <Reasoning isStreaming={status.type === "running"}>
    <ReasoningTrigger />
    <ReasoningContent>{text}</ReasoningContent>
  </Reasoning>
);

function toolUIState(
  statusType: "running" | "complete" | "incomplete" | "requires-action",
  result: unknown,
): ToolUIPart["state"] {
  if (result !== undefined) return "output-available";
  if (statusType === "running") return "input-available";
  if (statusType === "requires-action") return "input-available";
  if (statusType === "incomplete") return "output-error";
  return "input-streaming";
}

const ToolCall: ToolCallMessagePartComponent<unknown, unknown> = ({
  toolName,
  args,
  result,
  status,
}) => {
  const state = toolUIState(status.type, result);
  const errorText =
    status.type === "incomplete" && "error" in status && status.error != null
      ? String(status.error)
      : undefined;
  return (
    <Tool data-testid="tool-call-part">
      <ToolHeader title={toolName} type={`tool-${toolName}`} state={state} />
      <ToolContent>
        <ToolInput input={args as ToolUIPart["input"]} />
        <ToolOutput output={result} errorText={errorText} />
      </ToolContent>
    </Tool>
  );
};

const dataByName: Record<string, DataMessagePartComponent<unknown>> = {};
for (const kind of Object.keys(dataPartComponents)) {
  const kindTyped = kind as DataPartKind;
  const shortName = kindTyped.startsWith(DATA_PREFIX)
    ? kindTyped.slice(DATA_PREFIX.length)
    : kindTyped;
  dataByName[shortName] = (({ data }: { data: unknown }) => (
    <DataPartRenderer kind={kindTyped} data={data} />
  )) as DataMessagePartComponent<unknown>;
}

const reportedUnknownDataKinds = new Set<string>();

const UnknownDataPartError: DataMessagePartComponent<unknown> = ({ name }) => {
  if (!reportedUnknownDataKinds.has(name)) {
    reportedUnknownDataKinds.add(name);
    toast.error(`Unknown data part: data-${name}`, {
      description:
        "No renderer registered for this kind. Add one in " +
        "content/contentComponents.ts or stop emitting it from the backend.",
    });
  }
  return null;
};

const contentComponents = {
  Text,
  Reasoning: ReasoningPart,
  tools: { by_name: { think: ToolThink }, Fallback: ToolCall },
  data: { by_name: dataByName, Fallback: UnknownDataPartError },
} as const;

const MESSAGE_FADE_IN = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.2, ease: "easeOut" as const },
};

export function UserMessage() {
  return (
    <motion.div {...MESSAGE_FADE_IN}>
      <Message from="user">
        <MessageContent>
          <MessagePrimitive.Content components={contentComponents} />
        </MessageContent>
        <ActionBarPrimitive.Root asChild hideWhenRunning>
          <MessageActions className="justify-end opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
            <ActionBarPrimitive.Copy asChild>
              <MessageAction tooltip="Copy">
                <Copy />
              </MessageAction>
            </ActionBarPrimitive.Copy>
            <ActionBarPrimitive.Edit asChild>
              <MessageAction tooltip="Edit">
                <Pencil />
              </MessageAction>
            </ActionBarPrimitive.Edit>
          </MessageActions>
        </ActionBarPrimitive.Root>
      </Message>
    </motion.div>
  );
}

export function UserEditComposer() {
  const isLast = useMessage((s) => s.isLast);
  return (
    <motion.div {...MESSAGE_FADE_IN}>
      <Message from="user">
        <ComposerPrimitive.Root className="ml-auto flex w-full max-w-2xl flex-col gap-2 rounded-lg border bg-card px-3 py-2">
          <ComposerPrimitive.Input
            autoFocus
            className="w-full resize-none bg-transparent text-sm outline-none"
          />
          <div className="flex justify-end gap-2">
            <ComposerPrimitive.Cancel asChild>
              <Button type="button" variant="ghost" size="sm">
                <X className="mr-1 h-3.5 w-3.5" /> Cancel
              </Button>
            </ComposerPrimitive.Cancel>
            {isLast ? (
              <ComposerPrimitive.Send asChild>
                <Button type="button" size="sm">
                  <Check className="mr-1 h-3.5 w-3.5" /> Save
                </Button>
              </ComposerPrimitive.Send>
            ) : (
              <EditComposerBranchOrRevert />
            )}
          </div>
        </ComposerPrimitive.Root>
      </Message>
    </motion.div>
  );
}

function selectAssistantPlaceholderVisible(m: ThreadMessage): boolean {
  if (m.status?.type !== "running") return false;
  for (const part of m.content) {
    if (part.type === "text" && part.text.length > 0) return false;
    if (part.type === "reasoning" && part.text.length > 0) return false;
    if (part.type === "tool-call") return false;
    if (part.type === "data") return false;
  }
  return true;
}

function AssistantThinkingPlaceholder() {
  const visible = useMessage({
    optional: true,
    selector: selectAssistantPlaceholderVisible,
  });
  if (visible !== true) return null;
  return (
    <Shimmer as="span" className="text-sm font-medium" duration={1.2}>
      Thinking...
    </Shimmer>
  );
}

const ASSISTANT_ERROR_DEFAULT = "The model couldn't finish this turn.";

function selectAssistantErrorDetail(m: ThreadMessage): string | null {
  if (m.status?.type !== "incomplete") return null;
  if (m.status.reason === "cancelled") return null;
  const raw = m.status.error;
  if (typeof raw === "string" && raw.length > 0) return raw;
  if (
    raw !== null
    && typeof raw === "object"
    && "message" in raw
    && typeof (raw as { message?: unknown }).message === "string"
  ) {
    return (raw as { message: string }).message;
  }
  return ASSISTANT_ERROR_DEFAULT;
}

function AssistantErrorCard() {
  const detail = useMessage({
    optional: true,
    selector: selectAssistantErrorDetail,
  });
  if (typeof detail !== "string") return null;
  return (
    <div
      data-testid="assistant-error-card"
      className="my-2 flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium">Response failed</p>
        <p className="mt-0.5 break-words text-xs text-destructive/80">
          {detail}
        </p>
        <ActionBarPrimitive.Reload asChild>
          <button
            type="button"
            className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-destructive/40 bg-background px-2 py-1 text-xs font-medium text-destructive shadow-sm transition-colors hover:bg-destructive/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive"
          >
            <RefreshCw className="size-3" aria-hidden />
            Try again
          </button>
        </ActionBarPrimitive.Reload>
      </div>
    </div>
  );
}

export function AssistantMessage() {
  return (
    <motion.div {...MESSAGE_FADE_IN}>
      <Message from="assistant">
        <MessageContent>
          <ModelBadge />
          <AssistantThinkingPlaceholder />
          <MessagePrimitive.Content components={contentComponents} />
          <AssistantErrorCard />
        </MessageContent>
        <ActionBarPrimitive.Root asChild hideWhenRunning>
          <MessageActions className="opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
            <ActionBarPrimitive.Copy asChild>
              <MessageAction tooltip="Copy response">
                <Copy />
              </MessageAction>
            </ActionBarPrimitive.Copy>
            <ActionBarPrimitive.Reload asChild>
              <MessageAction tooltip="Regenerate">
                <RefreshCw />
              </MessageAction>
            </ActionBarPrimitive.Reload>
            <ActionBarPrimitive.FeedbackPositive asChild>
              <MessageAction tooltip="Good response">
                <ThumbsUp />
              </MessageAction>
            </ActionBarPrimitive.FeedbackPositive>
            <ActionBarPrimitive.FeedbackNegative asChild>
              <MessageAction tooltip="Bad response">
                <ThumbsDown />
              </MessageAction>
            </ActionBarPrimitive.FeedbackNegative>
            <BranchMessageAction />
          </MessageActions>
        </ActionBarPrimitive.Root>
      </Message>
    </motion.div>
  );
}
