"use client";

import { useQuery } from "@tanstack/react-query";
import { redirect, useParams } from "next/navigation";

import { conversationDetailOptions } from "@/lib/api/conversations";
import { conversationMessagesOptions } from "@/lib/api/conversationMessages";
import { Spinner } from "@/components/ui/spinner";
import { useSessionStore } from "@/state/useSessionStore";

import { ChatThread } from "./ChatThread";
import { RightRail } from "./rail/RightRail";

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

  const detailQuery = useQuery(conversationDetailOptions(conversationId));
  const messagesQuery = useQuery({
    ...conversationMessagesOptions(conversationId),
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
    <div className="flex min-h-0 min-w-0 flex-1">
      <div className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-card">
        <ChatThread
          key={`${conversationId}:${chatResetCounter}`}
          conversationId={conversationId}
          initialMessages={messagesQuery.data ?? []}
        />
      </div>
      <RightRail
        conversationId={conversationId}
        strategy={strategy}
        siteId={siteId}
      />
    </div>
  );
}
