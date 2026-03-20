import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/app/api/v1/_proxy", () => ({
  proxySSEGet: vi.fn(async () => new Response("data: ok\n\n", { status: 200 })),
}));

import { NextRequest } from "next/server";

import { proxySSEGet } from "@/app/api/v1/_proxy";
import { GET } from "./route";

const proxyMock = vi.mocked(proxySSEGet);

function makeReq(
  path: string,
  init?: { method?: string; body?: string; headers?: Record<string, string> },
): NextRequest {
  return new NextRequest(new URL(path, "http://localhost:3000"), init);
}

describe("GET /api/v1/operations/:id/subscribe", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies SSE GET to the correct upstream path", async () => {
    const req = makeReq("/api/v1/operations/op-123/subscribe");
    await GET(req, {
      params: Promise.resolve({ id: "op-123" }),
    });

    expect(proxyMock).toHaveBeenCalledOnce();
    const call1 = proxyMock.mock.calls[0];
    if (call1 === undefined) throw new Error("proxy was not called");
    const [, path] = call1;
    expect(path).toBe("/api/v1/operations/op-123/subscribe");
  });

  it("forwards query parameters (e.g. catchup cursor)", async () => {
    const req = makeReq("/api/v1/operations/op-123/subscribe?after=42");
    await GET(req, {
      params: Promise.resolve({ id: "op-123" }),
    });

    const call2 = proxyMock.mock.calls[0];
    if (call2 === undefined) throw new Error("proxy was not called");
    const [, path] = call2;
    expect(path).toBe("/api/v1/operations/op-123/subscribe?after=42");
  });
});
