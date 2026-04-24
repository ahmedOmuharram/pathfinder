"use client";

import {
  AssistantRuntimeProvider,
  ThreadPrimitive,
  useAuiEvent,
} from "@assistant-ui/react";
import type { UIMessage } from "ai";
import { useState } from "react";

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { useSessionStore } from "@/state/useSessionStore";

import { ChatEmptyState } from "./ChatEmptyState";
import { Composer } from "./composer/Composer";
import {
  AssistantMessage,
  UserEditComposer,
  UserMessage,
} from "./content/MessageRenderer";
import { useChatRuntime } from "./runtime/useChatRuntime";

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
  initialMessages,
  allowMissing = false,
}: {
  conversationId: string;
  initialMessages?: UIMessage[];
  allowMissing?: boolean;
}) {
  const runtime = useChatRuntime({
    conversationId,
    allowMissing,
    ...(initialMessages !== undefined && { initialMessages }),
  });
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
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatUrlSync conversationId={conversationId} />
      <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col">
        <Conversation>
          <ConversationContent>
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
        <Composer conversationId={conversationId} />
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}
