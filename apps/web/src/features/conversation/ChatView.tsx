"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useQuery } from "@tanstack/react-query";
import type { UIMessage } from "ai";
import { redirect, useParams } from "next/navigation";

import type { Strategy } from "@pathfinder/shared";
import { strategyQueryOptions } from "@/lib/api/strategy";
import { conversationSnapshotOptions } from "@/lib/api/conversationSnapshot";
import { Spinner } from "@/components/ui/spinner";
import { useSessionStore } from "@/state/useSessionStore";

import { ChatThread } from "./ChatThread";
import { RightRail } from "./rail/RightRail";
import { ChatHelpersProvider } from "./runtime/chatHelpersContext";
import { useChatRuntime } from "./runtime/useChatRuntime";

export function ChatView({
  conversationId,
  allowMissing = false,
}: {
  conversationId: string;
  allowMissing?: boolean;
}) {
  const params = useParams<{ siteId?: string }>();
  const siteSegment = params.siteId ?? "";
  const chatResetCounter = useSessionStore((s) => s.chatResetCounter);

  const detailQuery = useQuery(strategyQueryOptions(conversationId));
  const messagesQuery = useQuery({
    ...conversationSnapshotOptions(conversationId),
    enabled: allowMissing || detailQuery.data != null,
  });

  if (
    !allowMissing &&
    detailQuery.isFetched &&
    detailQuery.data === null
  ) {
    redirect(`/${siteSegment}/conversation`);
  }

  if (detailQuery.isPending || messagesQuery.isPending) {
    return (
      <div className="flex h-full items-center justify-center bg-card">
        <Spinner className="size-5" />
      </div>
    );
  }

  const strategy = detailQuery.data ?? null;
  const siteId = strategy?.siteId ?? "";

  return (
    <ChatViewBody
      key={`${conversationId}:${chatResetCounter}`}
      conversationId={conversationId}
      initialMessages={messagesQuery.data ?? []}
      allowMissing={allowMissing}
      strategy={strategy}
      siteId={siteId}
    />
  );
}

function ChatViewBody({
  conversationId,
  initialMessages,
  allowMissing,
  strategy,
  siteId,
}: {
  conversationId: string;
  initialMessages: UIMessage[];
  allowMissing: boolean;
  strategy: Strategy | null;
  siteId: string;
}) {
  const { runtime, chat } = useChatRuntime({
    conversationId,
    allowMissing,
    initialMessages,
  });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatHelpersProvider value={chat}>
        <div className="flex min-h-0 min-w-0 flex-1">
          <div className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-card">
            <ChatThread conversationId={conversationId} />
          </div>
          <RightRail
            conversationId={conversationId}
            strategy={strategy}
            siteId={siteId}
          />
        </div>
      </ChatHelpersProvider>
    </AssistantRuntimeProvider>
  );
}
