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
  chatId: string;
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
  const chatId = chatIdFromUrl ?? generatedChatId;
  const allowMissing = chatId === generatedChatId;
  return { chatId, allowMissing };
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

  const { chatId, allowMissing } = computeChatResolution({
    pathname,
    generatedChatId,
  });

  return <ChatView chatId={chatId} allowMissing={allowMissing} />;
}
