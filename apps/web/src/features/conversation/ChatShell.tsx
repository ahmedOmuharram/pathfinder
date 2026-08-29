"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

import { ChatView } from "./ChatView";

const CHAT_ID_FROM_PATH = /\/conversation\/([^/]+)/;
const STRATEGY_PATH = /\/conversation\/[^/]+\/strategy(\/|$)/;
const EDA_PATH = /\/conversation\/[^/]+\/eda(\/|$)/;

function extractChatId(pathname: string): string | null {
  const match = pathname.match(CHAT_ID_FROM_PATH);
  return match?.[1] ?? null;
}

export function isStrategyRoute(pathname: string): boolean {
  return STRATEGY_PATH.test(pathname);
}

export function isEdaRoute(pathname: string): boolean {
  return EDA_PATH.test(pathname);
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

  // A route that owns the main pane renders its own page instead of the thread.
  if (isStrategyRoute(pathname) || isEdaRoute(pathname)) return null;

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
