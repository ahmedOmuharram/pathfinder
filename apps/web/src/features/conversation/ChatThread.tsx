"use client";

import { AssistantRuntimeProvider, ThreadPrimitive } from "@assistant-ui/react";
import type { UIMessage } from "ai";

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";

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
