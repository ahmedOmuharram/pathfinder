"use client";

import { useQuery } from "@tanstack/react-query";
import { redirect } from "next/navigation";
import { parseAsString, useQueryState } from "nuqs";

import {
  conversationDetailOptions,
  conversationMessagesOptions,
} from "@/lib/api/conversations";
import { Spinner } from "@/components/ui/spinner";
import { StrategyGraph } from "@/features/strategy/graph/components/StrategyGraph";

import { ChatThread } from "./ChatThread";
import { BranchSwitcher } from "./branches/BranchSwitcher";

export function ChatView({
  chatId,
  allowMissing = false,
}: {
  chatId: string;
  allowMissing?: boolean;
}) {
  const [activeBranch] = useQueryState("branch", parseAsString);

  const detailQuery = useQuery(conversationDetailOptions(chatId));
  const messagesQuery = useQuery({
    ...conversationMessagesOptions(chatId),
    enabled: allowMissing || detailQuery.data != null,
  });

  if (
    !allowMissing &&
    detailQuery.isFetched &&
    detailQuery.data === null
  ) {
    redirect("/conversation");
  }

  if (detailQuery.isPending || messagesQuery.isPending) {
    return (
      <div className="flex h-full items-center justify-center bg-card">
        <Spinner className="size-5" />
      </div>
    );
  }

  async function getCheckpointId(): Promise<string | null> {
    return activeBranch;
  }

  const strategy = detailQuery.data;
  const showGraph = strategy != null && strategy.steps.length > 0;

  return (
    <div className="flex min-h-0 min-w-0 flex-1">
      <div className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-card">
        <div className="flex items-center justify-end border-b border-border px-3 py-1.5">
          <BranchSwitcher chatId={chatId} />
        </div>
        <ChatThread
          chatId={chatId}
          initialMessages={messagesQuery.data ?? []}
          getCheckpointId={getCheckpointId}
        />
      </div>
      {showGraph && (
        <div className="flex min-h-0 w-1/2 shrink-0 flex-col border-l border-border bg-background">
          <StrategyGraph strategy={strategy} siteId={strategy.siteId} />
        </div>
      )}
    </div>
  );
}
