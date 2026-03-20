import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../_proxy", () => ({
  proxyJsonRequest: vi.fn(async () => new Response("{}", { status: 200 })),
}));

import { NextRequest } from "next/server";

import { proxyJsonRequest } from "../_proxy";
import { POST } from "./route";

const proxyMock = vi.mocked(proxyJsonRequest);

function makeReq(
  path: string,
  init?: { method?: string; body?: string; headers?: Record<string, string> },
): NextRequest {
  return new NextRequest(new URL(path, "http://localhost:3000"), init);
}

describe("POST /api/v1/chat", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies to /api/v1/chat with includeBody: true", async () => {
    const req = makeReq("/api/v1/chat", {
      method: "POST",
      body: '{"message":"hello","conversationId":"c1"}',
      headers: { "content-type": "application/json" },
    });
    await POST(req);

    expect(proxyMock).toHaveBeenCalledOnce();
    const call = proxyMock.mock.calls[0];
    if (call === undefined) throw new Error("proxy was not called");
    const [passedReq, path, opts] = call;
    expect(passedReq).toBe(req);
    expect(path).toBe("/api/v1/chat");
    expect(opts).toEqual({ includeBody: true });
  });
});
