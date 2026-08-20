import { type UIMessage, type UIMessageChunk } from "ai";
import { describe, expect, it } from "vitest";

import { DurableChatTransport } from "./DurableChatTransport";

/**
 * The chat SSE stream sends `: keep-alive` comment frames while a turn is
 * queued or silent. A comment that reached the chunk schema would kill the
 * stream, so the transport has to drop it and pass the real frames through
 * unchanged.
 */

class ProbeTransport extends DurableChatTransport<UIMessage> {
  parse(body: string): ReadableStream<UIMessageChunk> {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(body));
        controller.close();
      },
    });
    return this.processResponseStream(stream);
  }
}

async function chunksOf(body: string): Promise<UIMessageChunk[]> {
  const transport = new ProbeTransport({
    api: "/api/v1/chat",
    conversationId: "c1",
    eventsUrlFor: (id) => `/api/v1/conversations/${id}/events`,
  });
  const reader = transport.parse(body).getReader();
  const chunks: UIMessageChunk[] = [];
  let next = await reader.read();
  while (next.done !== true) {
    chunks.push(next.value);
    next = await reader.read();
  }
  return chunks;
}

const QUEUED = '{"type":"data-turn-status","data":{"label":"Queued"}}';
const START = '{"type":"start","messageId":"m1"}';

describe("processResponseStream", () => {
  it("drops keep-alive comments and keeps every real chunk", async () => {
    const body =
      `id: 1\ndata: ${QUEUED}\n\n` +
      ": keep-alive\n\n" +
      ": keep-alive\n\n" +
      `id: 2\ndata: ${START}\n\n` +
      "id: 3\ndata: [DONE]\n\n";

    expect(await chunksOf(body)).toEqual([
      { type: "data-turn-status", data: { label: "Queued" } },
      { type: "start", messageId: "m1" },
    ]);
  });

  it("survives a stream that is nothing but keep-alives", async () => {
    const body = ": keep-alive\n\n: keep-alive\n\n";

    expect(await chunksOf(body)).toEqual([]);
  });

  it("still dies on a data frame the chunk schema rejects", async () => {
    // The reason the keep-alive is a comment and not a data frame.
    const body = `id: 1\ndata: ${START}\n\nid: 2\ndata: keep-alive\n\n`;

    await expect(chunksOf(body)).rejects.toThrow();
  });
});
