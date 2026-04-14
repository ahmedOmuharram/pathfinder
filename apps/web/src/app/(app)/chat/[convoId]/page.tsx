"use client";

import { useParams } from "next/navigation";

import { ChatView } from "@/features/chat/ChatView";

export default function ChatConvoPage() {
  const params = useParams<{ convoId: string }>();
  return <ChatView chatId={params.convoId} />;
}
