"use client";

/**
 * Shares the `useChat` return value (the AI SDK v6 `ChatSession`) with deeply
 * nested part renderers so they can call methods like
 * `addToolApprovalResponse` without prop drilling.
 *
 * The provider is mounted by the chat panel (Task 5h); consumers throw if used
 * outside it — this is intentional fail-fast behavior so that a missing
 * provider surfaces immediately during development rather than silently
 * no-oping at runtime.
 */

import { createContext, useContext, type ReactNode } from "react";

import type { useChat } from "@ai-sdk/react";

import type { PathfinderUIMessage } from "@pathfinder/shared";

type ChatSession = ReturnType<typeof useChat<PathfinderUIMessage>>;

const ChatSessionContext = createContext<ChatSession | null>(null);

export function ChatSessionProvider({
  session,
  children,
}: {
  session: ChatSession;
  children: ReactNode;
}) {
  return (
    <ChatSessionContext.Provider value={session}>
      {children}
    </ChatSessionContext.Provider>
  );
}

export function useChatSessionContext(): ChatSession {
  const ctx = useContext(ChatSessionContext);
  if (ctx === null) {
    throw new Error(
      "useChatSessionContext must be used inside a ChatSessionProvider",
    );
  }
  return ctx;
}
