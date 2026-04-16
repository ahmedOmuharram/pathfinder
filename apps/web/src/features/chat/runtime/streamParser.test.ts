import { describe, it, expect } from "vitest";

import { parseSseStream } from "./streamParser";

function mockResponse(raw: string): Response {
  const enc = new TextEncoder().encode(raw);
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(enc);
      controller.close();
    },
  });
  return new Response(stream, {
    headers: { "content-type": "text/event-stream" },
  });
}

function mockChunkedResponse(chunks: string[]): Response {
  const enc = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
  return new Response(stream, {
    headers: { "content-type": "text/event-stream" },
  });
}

describe("parseSseStream", () => {
  it("parses a single stream event", async () => {
    const raw = 'event: stream\ndata: {"type":"done","reason":"completed"}\n\n';
    const events: unknown[] = [];
    for await (const ev of parseSseStream(mockResponse(raw))) events.push(ev);
    expect(events).toHaveLength(1);
    const first = events[0] as { type: string };
    expect(first.type).toBe("done");
  });

  it("parses multiple events split across chunks", async () => {
    const chunks = [
      'event: stream\ndata: {"type":"messages/partial","messageId":"m","delta":"Hi"',
      "}\n\n",
      'event: stream\ndata: {"type":"done","reason":"completed"}\n\n',
    ];
    const events: unknown[] = [];
    for await (const ev of parseSseStream(mockChunkedResponse(chunks))) {
      events.push(ev);
    }
    expect(events).toHaveLength(2);
    const first = events[0] as { type: string };
    const second = events[1] as { type: string };
    expect(first.type).toBe("messages/partial");
    expect(second.type).toBe("done");
  });

  it("ignores non-stream SSE events", async () => {
    const raw = 'event: heartbeat\ndata: {"type":"done"}\n\n';
    const events: unknown[] = [];
    for await (const ev of parseSseStream(mockResponse(raw))) events.push(ev);
    expect(events).toHaveLength(0);
  });
});
