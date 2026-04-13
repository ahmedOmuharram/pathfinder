import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/app/api/v1/_proxy", () => ({
  proxyJsonRequest: vi.fn(async () => new Response("{}", { status: 202 })),
}));

import { NextRequest } from "next/server";

import { proxyJsonRequest } from "@/app/api/v1/_proxy";
import { POST } from "./route";

const proxyMock = vi.mocked(proxyJsonRequest);

describe("POST /api/v1/strategies/[id]/plan-actions", () => {
  beforeEach(() => proxyMock.mockClear());

  it("proxies the request body to the backend plan-actions route", async () => {
    const req = new NextRequest(
      new URL("http://localhost:3000/api/v1/strategies/abc/plan-actions"),
      {
        method: "POST",
        body: JSON.stringify({ action: "approve", planId: "plan_1" }),
        headers: { "content-type": "application/json" },
      },
    );

    await POST(req, { params: Promise.resolve({ id: "abc" }) });

    expect(proxyMock).toHaveBeenCalledOnce();
    const firstCall = proxyMock.mock.calls[0];
    expect(firstCall).toBeDefined();
    if (!firstCall) {
      throw new Error("proxyJsonRequest was not called");
    }
    const [, path, opts] = firstCall;
    expect(path).toBe("/api/v1/strategies/abc/plan-actions");
    expect(opts).toEqual({ includeBody: true });
  });
});
