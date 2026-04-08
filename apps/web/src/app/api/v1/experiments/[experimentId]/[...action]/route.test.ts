import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../_proxy", () => ({
  proxyJsonRequest: vi.fn(async () => new Response("{}", { status: 200 })),
}));

import { NextRequest } from "next/server";

import { proxyJsonRequest } from "../../../_proxy";
import { GET, POST } from "./route";

const proxyMock = vi.mocked(proxyJsonRequest);

function lastCall() {
  const call = proxyMock.mock.calls[0];
  if (call == null) throw new Error("proxyJsonRequest was not called");
  return call;
}

type Ctx = { params: Promise<{ experimentId: string; action: string[] }> };

function makeReq(
  path: string,
  init?: { method?: string; body?: string; headers?: Record<string, string> },
): NextRequest {
  return new NextRequest(new URL(path, "http://localhost:3000"), init);
}

function ctx(experimentId: string, action: string[]): Ctx {
  return { params: Promise.resolve({ experimentId, action }) };
}

describe("GET /api/v1/experiments/:experimentId/:action", () => {
  beforeEach(() => proxyMock.mockClear());

  it("builds upstream path from experimentId and single action segment", async () => {
    const req = makeReq("/api/v1/experiments/exp-1/cross-validate");
    await GET(req, ctx("exp-1", ["cross-validate"]));

    const [, path] = lastCall();
    expect(path).toBe("/api/v1/experiments/exp-1/cross-validate");
  });

  it("builds upstream path with multiple action segments", async () => {
    const req = makeReq("/api/v1/experiments/exp-1/importable-strategies/details");
    await GET(req, ctx("exp-1", ["importable-strategies", "details"]));

    const [, path] = lastCall();
    expect(path).toBe("/api/v1/experiments/exp-1/importable-strategies/details");
  });

  it("encodes special characters in experimentId and action segments", async () => {
    const req = makeReq("/api/v1/experiments/exp%2F1/my%20action");
    await GET(req, ctx("exp/1", ["my action"]));

    const [, path] = lastCall();
    expect(path).toBe("/api/v1/experiments/exp%2F1/my%20action");
  });

  it("forwards query parameters", async () => {
    const req = makeReq("/api/v1/experiments/exp-1/enrich?recordType=gene");
    await GET(req, ctx("exp-1", ["enrich"]));

    const [, path] = lastCall();
    expect(path).toBe("/api/v1/experiments/exp-1/enrich?recordType=gene");
  });
});

describe("POST /api/v1/experiments/:experimentId/:action", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies POST with includeBody: true", async () => {
    const req = makeReq("/api/v1/experiments/exp-1/enrich", {
      method: "POST",
      body: '{"geneList":[]}',
      headers: { "content-type": "application/json" },
    });
    await POST(req, ctx("exp-1", ["enrich"]));

    const [, path, opts] = lastCall();
    expect(path).toBe("/api/v1/experiments/exp-1/enrich");
    expect(opts).toEqual({ method: "POST", includeBody: true });
  });
});
