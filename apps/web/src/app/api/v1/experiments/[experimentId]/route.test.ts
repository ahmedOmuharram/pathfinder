import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../_proxy", () => ({
  proxyJsonRequest: vi.fn(async () => new Response("{}", { status: 200 })),
}));

import { NextRequest } from "next/server";

import { proxyJsonRequest } from "../../_proxy";
import { DELETE, GET, PATCH, POST } from "./route";

const proxyMock = vi.mocked(proxyJsonRequest);

type Ctx = { params: Promise<{ experimentId: string }> };

function makeReq(
  path: string,
  init?: { method?: string; body?: string; headers?: Record<string, string> },
): NextRequest {
  return new NextRequest(new URL(path, "http://localhost:3000"), init);
}

function ctx(experimentId: string): Ctx {
  return { params: Promise.resolve({ experimentId }) };
}

function getFirstCall() {
  const calls = proxyMock.mock.calls;
  if (calls.length === 0) {
    throw new Error("Expected at least one mock call");
  }
  const call = calls[0];
  if (!call) {
    throw new Error("Expected at least one mock call");
  }
  return call;
}

describe("GET /api/v1/experiments/:experimentId", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies to the correct upstream path", async () => {
    const req = makeReq("/api/v1/experiments/exp-123");
    await GET(req, ctx("exp-123"));

    expect(proxyMock).toHaveBeenCalledOnce();
    const path = getFirstCall()[1];
    expect(path).toBe("/api/v1/experiments/exp-123");
  });

  it("encodes special characters in experimentId", async () => {
    const req = makeReq("/api/v1/experiments/exp%2F123");
    await GET(req, ctx("exp/123"));

    const path = getFirstCall()[1];
    expect(path).toBe("/api/v1/experiments/exp%2F123");
  });

  it("forwards query parameters", async () => {
    const req = makeReq("/api/v1/experiments/exp-1?include=details");
    await GET(req, ctx("exp-1"));

    const path = getFirstCall()[1];
    expect(path).toBe("/api/v1/experiments/exp-1?include=details");
  });
});

describe("DELETE /api/v1/experiments/:experimentId", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies with method DELETE", async () => {
    const req = makeReq("/api/v1/experiments/exp-123", { method: "DELETE" });
    await DELETE(req, ctx("exp-123"));

    const call = getFirstCall();
    const path = call[1];
    const opts = call[2];
    expect(path).toBe("/api/v1/experiments/exp-123");
    expect(opts).toEqual({ method: "DELETE" });
  });
});

describe("PATCH /api/v1/experiments/:experimentId", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies with method PATCH and includeBody", async () => {
    const req = makeReq("/api/v1/experiments/exp-123", {
      method: "PATCH",
      body: '{"name":"updated"}',
      headers: { "content-type": "application/json" },
    });
    await PATCH(req, ctx("exp-123"));

    const call = getFirstCall();
    const path = call[1];
    const opts = call[2];
    expect(path).toBe("/api/v1/experiments/exp-123");
    expect(opts).toEqual({ method: "PATCH", includeBody: true });
  });
});

describe("POST /api/v1/experiments/:experimentId", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies with method POST and includeBody", async () => {
    const req = makeReq("/api/v1/experiments/exp-123", {
      method: "POST",
      body: '{"action":"run"}',
      headers: { "content-type": "application/json" },
    });
    await POST(req, ctx("exp-123"));

    const opts = getFirstCall()[2];
    expect(opts).toEqual({ method: "POST", includeBody: true });
  });

  it("appends suffix from URL pathname", async () => {
    const req = makeReq("/api/v1/experiments/exp-123/run", {
      method: "POST",
      body: "{}",
      headers: { "content-type": "application/json" },
    });
    await POST(req, ctx("exp-123"));

    const path = getFirstCall()[1];
    expect(path).toBe("/api/v1/experiments/exp-123/run");
  });
});
