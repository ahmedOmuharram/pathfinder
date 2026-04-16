"use client";

import { AssistantRuntimeProvider, ThreadPrimitive } from "@assistant-ui/react";
import type { LangChainMessage } from "@assistant-ui/react-langgraph";
import { nanoid } from "nanoid";
import { useState } from "react";

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";

import { ChatEmptyState } from "./ChatEmptyState";
import { Composer } from "./composer/Composer";
import {
  AssistantMessage,
  UserMessage,
} from "./content/MessageRenderer";
import {
  DataPartsStream,
  type DataPartEntry,
} from "./content/DataPartsStream";
import { useChatRuntime } from "./runtime/useLangGraphStream";

export function ChatThread({
  chatId,
  getCheckpointId,
}: {
  chatId: string;
  getCheckpointId?: (threadId: string, parentMessages: LangChainMessage[]) => Promise<string | null>;
}) {
  // Data parts (``data-phase-change``, ``data-task-progress``, etc.) arrive
  // as LangGraph custom events and have no messageId to hang on, so the
  // LangChain runtime has no place for them. Buffer locally in thread order
  // and render them under the message list as a typed stream.
  const [dataParts, setDataParts] = useState<DataPartEntry[]>([]);
  const onCustomEvent = (kind: string, data: unknown): void => {
    if (!kind.startsWith("data-")) return;
    setDataParts((prev) => [...prev, { id: nanoid(), kind, data }]);
  };

  const runtime = useChatRuntime({
    chatId,
    onCustomEvent,
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
                AssistantMessage,
              }}
            />
            <DataPartsStream parts={dataParts} />
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>
        <Composer />
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  );
}
