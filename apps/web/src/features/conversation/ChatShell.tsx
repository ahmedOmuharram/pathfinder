"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

import { ChatView } from "./ChatView";

const CHAT_ID_FROM_PATH = /\/conversation\/([^/]+)/;

function extractChatId(pathname: string): string | null {
  const match = pathname.match(CHAT_ID_FROM_PATH);
  return match?.[1] ?? null;
}

export interface ChatResolution {
  conversationId: string;
  allowMissing: boolean;
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
  return { conversationId, allowMissing };
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

  const { conversationId, allowMissing } = computeChatResolution({
    pathname,
    generatedChatId,
  });

  return <ChatView conversationId={conversationId} allowMissing={allowMissing} />;
}
