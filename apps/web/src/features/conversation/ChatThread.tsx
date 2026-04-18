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
  chatId,
  initialMessages,
  getCheckpointId,
}: {
  chatId: string;
  initialMessages?: UIMessage[];
  getCheckpointId?: (threadId: string, parentMessages: UIMessage[]) => Promise<string | null>;
}) {
  const runtime = useChatRuntime({
    chatId,
    ...(initialMessages !== undefined && { initialMessages }),
    ...(getCheckpointId !== undefined && { getCheckpointId }),
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
        <Composer />
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}
