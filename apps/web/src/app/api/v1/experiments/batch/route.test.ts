import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../_proxy", () => ({
  proxyJsonRequest: vi.fn(async () => new Response("{}", { status: 200 })),
}));

import { NextRequest } from "next/server";

import { proxyJsonRequest } from "../../_proxy";
import { POST } from "./route";

const proxyMock = vi.mocked(proxyJsonRequest);

function makeReq(
  path: string,
  init?: { method?: string; body?: string; headers?: Record<string, string> },
): NextRequest {
  return new NextRequest(new URL(path, "http://localhost:3000"), init);
}

describe("POST /api/v1/experiments/batch", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies to /api/v1/experiments/batch with includeBody: true", async () => {
    const req = makeReq("/api/v1/experiments/batch", {
      method: "POST",
      body: '{"experimentIds":["e1","e2"]}',
      headers: { "content-type": "application/json" },
    });
    await POST(req);

    expect(proxyMock).toHaveBeenCalledOnce();
    const firstCall = proxyMock.mock.calls[0];
    expect(firstCall).toBeDefined();
    if (firstCall == null) throw new Error("Expected proxyJsonRequest to be called");
    const [, path, opts] = firstCall;
    expect(path).toBe("/api/v1/experiments/batch");
    expect(opts).toEqual({ includeBody: true });
  });
});
