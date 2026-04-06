import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../_proxy", () => ({
  proxyJsonRequest: vi.fn(async () => new Response("{}", { status: 200 })),
}));

import { NextRequest } from "next/server";

import { proxyJsonRequest } from "../_proxy";
import { DELETE, GET, POST } from "./route";

const proxyMock = vi.mocked(proxyJsonRequest);

function makeReq(
  path: string,
  init?: { method?: string; body?: string; headers?: Record<string, string> },
): NextRequest {
  return new NextRequest(new URL(path, "http://localhost:3000"), init);
}

describe("GET /api/v1/experiments", () => {
  beforeEach(() => proxyMock.mockClear());
  afterEach(() => vi.restoreAllMocks());

  it("proxies to the upstream path without query string", async () => {
    const req = makeReq("/api/v1/experiments");
    await GET(req);

    expect(proxyMock).toHaveBeenCalledOnce();
    const [, path] = proxyMock.mock.calls[0]!;
    expect(path).toBe("/api/v1/experiments");
  });

  it("forwards query parameters to the upstream path", async () => {
    const req = makeReq("/api/v1/experiments?siteId=plasmodb&status=running");
    await GET(req);

    const [, path] = proxyMock.mock.calls[0]!;
    expect(path).toBe("/api/v1/experiments?siteId=plasmodb&status=running");
  });
});

describe("POST /api/v1/experiments", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies with includeBody: true", async () => {
    const req = makeReq("/api/v1/experiments", {
      method: "POST",
      body: '{"name":"test"}',
      headers: { "content-type": "application/json" },
    });
    await POST(req);

    expect(proxyMock).toHaveBeenCalledOnce();
    const [, path, opts] = proxyMock.mock.calls[0]!;
    expect(path).toBe("/api/v1/experiments");
    expect(opts).toEqual({ includeBody: true });
  });
});

describe("DELETE /api/v1/experiments", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies with method DELETE and forwards query params", async () => {
    const req = makeReq("/api/v1/experiments?id=abc&id=def", {
      method: "DELETE",
    });
    await DELETE(req);

    expect(proxyMock).toHaveBeenCalledOnce();
    const [, path, opts] = proxyMock.mock.calls[0]!;
    expect(path).toBe("/api/v1/experiments?id=abc&id=def");
    expect(opts).toEqual({ method: "DELETE" });
  });

  it("omits query string when no params present", async () => {
    const req = makeReq("/api/v1/experiments", { method: "DELETE" });
    await DELETE(req);

    const [, path] = proxyMock.mock.calls[0]!;
    expect(path).toBe("/api/v1/experiments");
  });
});
