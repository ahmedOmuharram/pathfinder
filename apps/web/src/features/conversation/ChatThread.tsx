"use client";

import {
  ThreadPrimitive,
  useAssistantRuntime,
  useAuiEvent,
} from "@assistant-ui/react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { conversationDetailOptions } from "@/lib/api/conversations";
import { useSessionStore } from "@/state/useSessionStore";

import { ChatEmptyState } from "./ChatEmptyState";
import { Composer } from "./composer/Composer";
import {
  AssistantMessage,
  UserEditComposer,
  UserMessage,
} from "./content/MessageRenderer";
import { SpecialistBanner } from "./specialists/SpecialistBanner";

function ChatUrlSync({ conversationId }: { conversationId: string }) {
  const siteId = useSessionStore((s) => s.selectedSite);
  useAuiEvent("thread.runStart", () => {
    if (typeof window === "undefined") return;
    const target = `/${siteId}/conversation/${conversationId}`;
    if (!window.location.pathname.startsWith(target)) {
      window.history.replaceState(null, "", target);
    }
  });
  return null;
}

export function ChatThread({
  conversationId,
}: {
  conversationId: string;
}) {
  const runtime = useAssistantRuntime();
  const pendingSubmission = useSessionStore((s) => s.pendingUserSubmission);
  const [firedContent, setFiredContent] = useState<string | null>(null);
  if (
    pendingSubmission !== null
    && pendingSubmission.conversationId === conversationId
    && firedContent !== pendingSubmission.content
  ) {
    const content = pendingSubmission.content;
    setFiredContent(content);
    queueMicrotask(() => {
      useSessionStore.getState().setPendingUserSubmission(null);
      runtime.thread.append(content);
    });
  }
  return (
    <>
      <ChatUrlSync conversationId={conversationId} />
      <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col">
        <SessionAwareBody conversationId={conversationId} />
        <Composer conversationId={conversationId} />
      </ThreadPrimitive.Root>
    </>
  );
}


function SessionAwareBody({ conversationId }: { conversationId: string }) {
  const { data } = useQuery(conversationDetailOptions(conversationId));
  const mode = data?.specialistMode;
  const sessionKind = mode?.kind ?? null;
  return (
    <>
      {mode != null ? (
        <SpecialistBanner conversationId={conversationId} mode={mode} />
      ) : null}
      <Conversation>
        <ConversationContent
          // The session-active attribute lets sibling CSS draw a
          // kind-tinted vertical rail down the left of every assistant +
          // system message rendered while a specialist session is open.
          // Combined with the bracket-styled entered/exited parts, this
          // delivers DOM-level visual grouping without replacing
          // assistant-ui's per-message renderer.
          data-session-active={sessionKind ?? undefined}
          className={
            sessionKind === "validate"
              ? "specialist-rail-validate"
              : sessionKind === "research"
                ? "specialist-rail-research"
                : undefined
          }
        >
          <ChatEmptyState />
          <ThreadPrimitive.Messages
            components={{
              UserMessage,
              UserEditComposer,
              AssistantMessage,
            }}
          />
        </ConversationContent>
        <ConversationScrollButton />
      </Conversation>
    </>
  );
}

