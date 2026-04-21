"use client";

import { AssistantRuntimeProvider, ThreadPrimitive } from "@assistant-ui/react";
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

export function ChatThread({
  conversationId,
  initialMessages,
}: {
  conversationId: string;
  initialMessages?: UIMessage[];
}) {
  const runtime = useChatRuntime({
    conversationId,
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
