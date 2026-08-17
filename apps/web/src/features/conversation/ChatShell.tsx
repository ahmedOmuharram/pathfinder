"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

import { ChatView } from "./ChatView";

const CHAT_ID_FROM_PATH = /\/conversation\/([^/]+)/;
const STRATEGY_PATH = /\/conversation\/[^/]+\/strategy(\/|$)/;

function extractChatId(pathname: string): string | null {
  const match = pathname.match(CHAT_ID_FROM_PATH);
  return match?.[1] ?? null;
}

export function isStrategyRoute(pathname: string): boolean {
  return STRATEGY_PATH.test(pathname);
}

export interface ChatResolution {
  conversationId: string;
  allowMissing: boolean;
  resumable: boolean;
}

export function computeChatResolution({
  pathname,
  generatedChatId,
}: {
  pathname: string;
  generatedChatId: string;
}): ChatResolution {
  const chatIdFromUrl = extractChatId(pathname);
  const conversationId = chatIdFromUrl ?? generatedChatId;
  const allowMissing = conversationId === generatedChatId;
  // A conversation named in the URL can have a turn running in it. Whether
  // this tab generated the id says nothing about that.
  return { conversationId, allowMissing, resumable: chatIdFromUrl !== null };
}

export function ChatShell() {
  const pathname = usePathname();
  const chatIdFromUrl = extractChatId(pathname);

  const [generatedChatId, setGeneratedChatId] = useState<string>(() =>
    crypto.randomUUID(),
  );
  const [lastSeenPath, setLastSeenPath] = useState<string>(pathname);

  if (chatIdFromUrl === null && lastSeenPath !== pathname) {
    setLastSeenPath(pathname);
    setGeneratedChatId(crypto.randomUUID());
  }

  // /conversation/[id]/strategy and nested routes own the main pane; let
  // the route's `page.tsx` render the strategy canvas instead of the chat.
  if (isStrategyRoute(pathname)) return null;

  const { conversationId, allowMissing, resumable } = computeChatResolution({
    pathname,
    generatedChatId,
  });

  return (
    <ChatView
      key={conversationId}
      conversationId={conversationId}
      allowMissing={allowMissing}
      resumable={resumable}
    />
  );
}
