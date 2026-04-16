/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { LangChainMessage } from "@assistant-ui/react-langgraph";

import { server } from "../../../../vitest.msw-setup";
import { runStreamForTest, useChatRuntime } from "./useLangGraphStream";

const SSE_BODY =
  'event: stream\ndata: {"type":"messages/partial","messageId":"m1","delta":"Hi"}\n\n' +
  'event: stream\ndata: {"type":"done","reason":"completed"}\n\n';

function sseResponse(body: string): Response {
  const enc = new TextEncoder().encode(body);
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(enc);
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

describe("useChatRuntime", () => {
  it("returns an assistant-ui runtime", () => {
    const { result } = renderHook(() => useChatRuntime({ chatId: "c1" }));
    expect(result.current).toBeDefined();
    expect(typeof result.current.thread).toBe("object");
  });

  it("posts to /api/v1/chat and yields parsed events", async () => {
    const calls: { url: string; body: unknown; headers: Headers }[] = [];
    server.use(
      http.post("http://localhost:3000/api/v1/chat", async ({ request }) => {
        calls.push({
          url: request.url,
          body: await request.json(),
          headers: request.headers,
        });
        return sseResponse(SSE_BODY);
      }),
    );

    const messages: LangChainMessage[] = [
      { type: "human", content: [{ type: "text", text: "Hello" }] },
    ];
    const events: { event: string; data: unknown }[] = [];
    for await (const ev of await runStreamForTest({
      chatId: "chat-123",
      messages,
    })) {
      events.push(ev);
    }

    expect(calls).toHaveLength(1);
    const call = calls[0];
    if (!call) throw new Error("no call recorded");
    expect(call.body).toMatchObject({
      chatId: "chat-123",
      message: "Hello",
    });
    // The body MUST NOT leak a userId — the backend reads the authenticated
    // user from the ``pathfinder-auth`` cookie only. A client-supplied
    // userId was historical plumbing and would be an impersonation vector
    // if anything downstream trusted it.
    expect((call.body as Record<string, unknown>)["userId"]).toBeUndefined();
    // CSRF: the backend middleware rejects state-changing requests lacking
    // this header with 403. The frontend must always send it — raw `fetch`
    // without `getAuthHeaders()` silently drops it.
    expect(call.headers.get("x-requested-with")).toBe("XMLHttpRequest");
    expect(call.headers.get("content-type")).toBe("application/json");
    expect(call.headers.get("accept")).toBe("text/event-stream");

    // "done" events are swallowed by toLangGraphIter — only message events yield
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({
      event: "messages/partial",
    });
  });

  it("includes parentCheckpointId when supplied", async () => {
    const captured: Record<string, unknown>[] = [];
    server.use(
      http.post("http://localhost:3000/api/v1/chat", async ({ request }) => {
        captured.push((await request.json()) as Record<string, unknown>);
        return sseResponse(
          'event: stream\ndata: {"type":"done","reason":"completed"}\n\n',
        );
      }),
    );

    const messages: LangChainMessage[] = [
      { type: "human", content: [{ type: "text", text: "Hi" }] },
    ];
    for await (const _ of await runStreamForTest({
      chatId: "chat-123",
      messages,
      parentCheckpointId: "ckpt_abc",
    })) {
      // drain
    }
    expect(captured).toHaveLength(1);
    const body = captured[0];
    if (!body) throw new Error("body not captured");
    expect(body).toMatchObject({
      chatId: "chat-123",
      message: "Hi",
      parentCheckpointId: "ckpt_abc",
    });
  });

  it("throws when /api/v1/chat returns a non-2xx status", async () => {
    server.use(
      http.post("http://localhost:3000/api/v1/chat", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );

    const messages: LangChainMessage[] = [
      { type: "human", content: [{ type: "text", text: "Hi" }] },
    ];
    await expect(
      runStreamForTest({
        chatId: "c1",
        messages,
      }),
    ).rejects.toThrow(/500/);
  });
});
