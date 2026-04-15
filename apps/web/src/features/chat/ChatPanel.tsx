"use client";

import { queryOptions, useQuery } from "@tanstack/react-query";

import { ChatSessionProvider } from "./approval/useChatContext";
import { ChatErrorBanner } from "./ChatErrorBanner";
import { useChatSession } from "./chat-hook";
import { ChatInput } from "./composer/ChatInput";
import { ModelPicker } from "./composer/ModelPicker";
import { ChatEmptyState } from "./EmptyState";
import { MessageList } from "./MessageList";
import { TaskListBadge } from "./TaskListBadge";
import { useConversationTitleSync } from "./useConversationTitleSync";
import { fetchChatHistory } from "@/lib/api/chat";
import { useSessionStore } from "@/state/useSessionStore";

function chatHistoryOptions(chatId: string) {
  return queryOptions({
    queryKey: ["chat", chatId, "messages"] as const,
    queryFn: () => fetchChatHistory(chatId),
    enabled: chatId.length > 0,
    staleTime: Number.POSITIVE_INFINITY,
  });
}

export function ChatPanel({
  chatId,
  mode,
}: {
  chatId: string;
  mode: "strategy" | "experiment";
}) {
  const selectedSite = useSessionStore((s) => s.selectedSite);
  const { data: history } = useQuery(chatHistoryOptions(chatId));
  const session = useChatSession(chatId, mode, history ?? []);
  const { messages, status, sendMessage, stop, error, regenerate, clearError } =
    session;

  const streaming = status === "streaming" || status === "submitted";
  const hasMessages = messages.length > 0;

  useConversationTitleSync({ chatId, messages, siteId: selectedSite });

  const handleSubmit = (text: string) => {
    if (!chatId) return;
    void sendMessage({ text });
  };

  return (
    <ChatSessionProvider session={session}>
      <div
        className="flex h-full min-h-0 flex-col bg-background"
        data-mode={mode}
        data-chat-id={chatId}
      >
        <div className="flex items-center justify-between border-b border-border px-4 py-2">
          <ModelPicker />
          <TaskListBadge />
        </div>

        <div className="relative min-h-0 flex-1">
          {hasMessages ? (
            <MessageList messages={messages} status={status} />
          ) : (
            <ChatEmptyState mode={mode} chatId={chatId} />
          )}
        </div>

        {error ? (
          <ChatErrorBanner
            error={error}
            onRetry={() => {
              clearError();
              void regenerate();
            }}
            onDismiss={clearError}
          />
        ) : null}

        <div className="border-t border-border p-3">
          <ChatInput
            onSubmit={handleSubmit}
            onStop={() => {
              void stop();
            }}
            disabled={streaming}
          />
        </div>
      </div>
    </ChatSessionProvider>
  );
}
