import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../_proxy", () => ({
  proxyJsonRequest: vi.fn(async () => new Response("{}", { status: 200 })),
}));

import { NextRequest } from "next/server";

import { proxyJsonRequest } from "../../_proxy";
import { POST } from "./route";

const proxyMock = vi.mocked(proxyJsonRequest);

describe("POST /api/v1/dev/login", () => {
  beforeEach(() => proxyMock.mockClear());

  it("preserves the query string when proxying to the backend dev login route", async () => {
    const req = new NextRequest(
      new URL("http://localhost:3000/api/v1/dev/login?user_id=worker-0"),
      { method: "POST" },
    );

    await POST(req);

    expect(proxyMock).toHaveBeenCalledOnce();
    const firstCall = proxyMock.mock.calls[0];
    expect(firstCall).toBeDefined();
    if (firstCall == null) throw new Error("Expected proxyJsonRequest to be called");
    const [, path] = firstCall;
    expect(path).toBe("/api/v1/dev/login?user_id=worker-0");
  });
});
