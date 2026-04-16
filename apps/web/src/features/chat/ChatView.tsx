"use client";

import { parseAsString, useQueryState } from "nuqs";

import { ChatThread } from "./ChatThread";
import { BranchSwitcher } from "./branches/BranchSwitcher";

export function ChatView({
  chatId,
}: {
  chatId: string;
}) {
  const [activeBranch] = useQueryState("branch", parseAsString);

  async function getCheckpointId(): Promise<string | null> {
    return activeBranch;
  }

  return (
    <div className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-card">
      <div className="flex items-center justify-end border-b border-border px-3 py-1.5">
        <BranchSwitcher chatId={chatId} />
      </div>
      <ChatThread chatId={chatId} getCheckpointId={getCheckpointId} />
    </div>
  );
}
