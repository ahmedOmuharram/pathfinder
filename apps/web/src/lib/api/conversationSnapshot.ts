import { queryOptions } from "@tanstack/react-query";
import { readUIMessageStream, type UIMessage, type UIMessageChunk } from "ai";
import { z } from "zod";

import { writeCursor } from "@/features/conversation/runtime/eventCursor";

import { APIError, requestJson } from "./http";

const SnapshotSchema = z.object({
  chunks: z.array(z.looseObject({ type: z.string() })),
  cursor: z.number(),
});

const USER_MESSAGE_TYPE = "user-message";

export async function loadSnapshotMessages(
  conversationId: string,
): Promise<UIMessage[]> {
  let snapshot: { chunks: unknown[]; cursor: number };
  try {
    snapshot = await requestJson(
      SnapshotSchema,
      `/api/v1/conversations/${conversationId}/events/snapshot`,
    );
  } catch (err) {
    if (err instanceof APIError && err.status === 404) return [];
    throw err;
  }
  writeCursor(conversationId, snapshot.cursor);
  return reduceSnapshotChunks(snapshot.chunks as ChunkLike[]);
}

interface ChunkLike {
  type: string;
  messageId?: string;
  message?: { id: string; role: "user"; parts: unknown[] };
}

export async function reduceSnapshotChunks(
  chunks: ChunkLike[],
): Promise<UIMessage[]> {
  const messages: UIMessage[] = [];
  let pending: ChunkLike[] = [];
  let pendingMessageId: string | undefined;
  const flush = async () => {
    if (pending.length === 0) return;
    messages.push(await reduceAssistantSlice(pending));
    pending = [];
    pendingMessageId = undefined;
  };
  for (const chunk of chunks) {
    if (chunk.type === USER_MESSAGE_TYPE) {
      await flush();
      const raw = chunk.message;
      if (raw != null) messages.push(raw as unknown as UIMessage);
      continue;
    }
    if (
      chunk.type === "start"
      && chunk.messageId != null
      && pendingMessageId != null
      && chunk.messageId !== pendingMessageId
    ) {
      await flush();
    }
    if (chunk.type === "start" && chunk.messageId != null) {
      pendingMessageId = chunk.messageId;
    }
    pending.push(chunk);
  }
  await flush();
  return messages;
}

async function reduceAssistantSlice(
  slice: ChunkLike[],
): Promise<UIMessage> {
  const stream = new ReadableStream<UIMessageChunk>({
    start(controller) {
      for (const chunk of slice) {
        controller.enqueue(chunk as unknown as UIMessageChunk);
      }
      controller.close();
    },
  });
  let last: UIMessage | undefined;
  for await (const message of readUIMessageStream({ stream })) {
    last = message;
  }
  if (last == null) {
    return {
      id: crypto.randomUUID(),
      role: "assistant",
      parts: [],
    } as unknown as UIMessage;
  }
  return last;
}

export function conversationSnapshotOptions(conversationId: string) {
  return queryOptions({
    queryKey: ["conversations", conversationId, "snapshot"] as const,
    queryFn: () => loadSnapshotMessages(conversationId),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}
