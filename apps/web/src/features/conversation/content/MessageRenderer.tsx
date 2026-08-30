"use client";

import {
  ActionBarPrimitive,
  ComposerPrimitive,
  MessagePrimitive,
  useAuiState,
  type DataMessagePartComponent,
  type ReasoningMessagePartComponent,
  type TextMessagePartComponent,
  type ThreadMessage,
} from "@assistant-ui/react";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy, Pencil, ThumbsDown, ThumbsUp, X } from "lucide-react";

import { BranchMessageAction } from "./BranchMessageAction";
import { EditComposerBranchOrRevert } from "./EditComposerSend";
import { RegenerateAction } from "./RegenerateAction";
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
import { Button } from "@/components/ui/button";

import { AssistantThinkingPlaceholder } from "./AssistantThinkingPlaceholder";
import { FailureNotice } from "./FailureNotice";
import { ModelBadge } from "./ModelBadge";
import { SupersededBadge } from "./SupersededBadge";
import { ConsultCarousel } from "./parts/ConsultCarousel";
import { StoppedNotice } from "./StoppedNotice";
import { dataPartRenderers } from "./dataPartRegistry";
import { TraceAnchor } from "../thread/TraceAnchor";

const markdownRemarkPlugins = [remarkGfm];

const Text: TextMessagePartComponent = () => (
  <MarkdownTextPrimitive
    remarkPlugins={markdownRemarkPlugins}
    className="prose prose-sm max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
  />
);

export const ReasoningPart: ReasoningMessagePartComponent = ({ text, status }) => {
  const streaming = status.type === "running";
  if (!streaming && text.trim() === "") return null;
  return (
    <Reasoning isStreaming={streaming}>
      <ReasoningTrigger />
      <ReasoningContent>{text}</ReasoningContent>
    </Reasoning>
  );
};

const reportedUnknownDataKinds = new Set<string>();

const UnknownDataPartError: DataMessagePartComponent<unknown> = ({ name }) => {
  if (!reportedUnknownDataKinds.has(name)) {
    reportedUnknownDataKinds.add(name);
    toast.error(`Unknown data part: data-${name}`, {
      description:
        "No renderer registered for this kind. Add one in content/coreDataParts.ts " +
        "or content/strategyDataParts.ts, or stop emitting it from the backend.",
    });
  }
  return null;
};

const contentComponents = {
  Text,
  Reasoning: ReasoningPart,
  tools: {
    by_name: { think: TraceAnchor },
    Fallback: TraceAnchor,
  },
  data: { by_name: dataPartRenderers, Fallback: UnknownDataPartError },
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
  const isLast = useAuiState((s) => s.message.isLast);
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

const ASSISTANT_ERROR_DEFAULT = "The model couldn't finish this turn.";

type FailureCarrier = {
  status?: { type: string; reason?: string; error?: unknown };
  content: readonly { type: string; name?: string }[];
};

function isFailedPart(part: { type: string; name?: string }): boolean {
  return (
    part.type === "data-turn-failed" ||
    (part.type === "data" && part.name === "turn-failed")
  );
}

/** The live error, or null when the turn already carries its durable
 * `data-turn-failed` part, which says the same thing and survives a reload. */
export function selectAssistantErrorDetail(m: FailureCarrier): string | null {
  if (m.status?.type !== "incomplete") return null;
  if (m.status.reason === "cancelled") return null;
  if (m.content.some(isFailedPart)) return null;
  const raw = m.status.error;
  if (typeof raw === "string" && raw.length > 0) return raw;
  if (
    raw !== null &&
    typeof raw === "object" &&
    "message" in raw &&
    typeof (raw as { message?: unknown }).message === "string"
  ) {
    return (raw as { message: string }).message;
  }
  return ASSISTANT_ERROR_DEFAULT;
}

function AssistantErrorCard() {
  const detail = useAuiState((s) => selectAssistantErrorDetail(s.message));
  if (typeof detail !== "string") return null;
  return <FailureNotice detail={detail} />;
}

function selectAssistantStopped(m: ThreadMessage): boolean {
  return m.status?.type === "incomplete" && m.status.reason === "cancelled";
}

function AssistantStoppedNotice() {
  const stopped = useAuiState((s) => selectAssistantStopped(s.message));
  if (stopped !== true) return null;
  return <StoppedNotice />;
}

export function AssistantMessage() {
  return (
    <motion.div {...MESSAGE_FADE_IN}>
      <Message from="assistant">
        <MessageContent>
          <ModelBadge />
          <SupersededBadge />
          <MessagePrimitive.Content components={contentComponents} />
          <ConsultCarousel />
          <AssistantThinkingPlaceholder />
          <AssistantErrorCard />
          <AssistantStoppedNotice />
        </MessageContent>
        <ActionBarPrimitive.Root asChild hideWhenRunning>
          <MessageActions className="opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
            <ActionBarPrimitive.Copy asChild>
              <MessageAction tooltip="Copy response">
                <Copy />
              </MessageAction>
            </ActionBarPrimitive.Copy>
            <ActionBarPrimitive.Reload asChild>
              <RegenerateAction />
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
