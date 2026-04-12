import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/app/api/v1/_proxy", () => ({
  proxyJsonRequest: vi.fn(async () => new Response("{}", { status: 200 })),
}));

import { NextRequest } from "next/server";

import { proxyJsonRequest } from "@/app/api/v1/_proxy";
import { GET } from "./route";

const proxyMock = vi.mocked(proxyJsonRequest);

function makeReq(
  path: string,
  init?: { method?: string; body?: string; headers?: Record<string, string> },
): NextRequest {
  return new NextRequest(new URL(path, "http://localhost:3000"), init);
}

describe("GET /api/v1/operations/active", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies to upstream without query params", async () => {
    const req = makeReq("/api/v1/operations/active");
    await GET(req);

    expect(proxyMock).toHaveBeenCalledOnce();
    const call = proxyMock.mock.calls[0];
    expect(call).toBeDefined();
    if (!call) {
      throw new Error("Expected proxyJsonRequest to be called");
    }
    const [, path] = call;
    expect(path).toBe("/api/v1/operations/active");
  });

  it("forwards query parameters to upstream", async () => {
    const req = makeReq("/api/v1/operations/active?siteId=plasmodb");
    await GET(req);

    const call = proxyMock.mock.calls[0];
    expect(call).toBeDefined();
    if (!call) {
      throw new Error("Expected proxyJsonRequest to be called");
    }
    const [, path] = call;
    expect(path).toBe("/api/v1/operations/active?siteId=plasmodb");
  });
});
