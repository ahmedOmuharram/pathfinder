import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

vi.mock("./auth", () => {
  return {
    getAuthToken: () => "test-token",
  };
});

import { APIError, buildUrl, getAuthHeaders, requestJson } from "./http";

function makeHeaders(init: Record<string, string>) {
  const normalized = new Map<string, string>();
  for (const [k, v] of Object.entries(init)) normalized.set(k.toLowerCase(), v);
  return {
    get(name: string) {
      return normalized.get(name.toLowerCase()) ?? null;
    },
  } as Headers;
}

function makeResponse(args: {
  ok: boolean;
  status: number;
  statusText: string;
  headers?: Record<string, string>;
  json?: unknown;
  text?: string;
}): Response {
  const headers = makeHeaders(args.headers ?? {});
  return {
    ok: args.ok,
    status: args.status,
    statusText: args.statusText,
    headers,
    async json() {
      return args.json;
    },
    async text() {
      return args.text ?? "";
    },
  } as unknown as Response;
}

describe("lib/api/http", () => {
  const ORIGINAL_ENV = { ...process.env };

  beforeEach(() => {
    process.env = { ...ORIGINAL_ENV };
  });

  afterEach(() => {
    process.env = { ...ORIGINAL_ENV };
    vi.unstubAllGlobals();
  });

  it("buildUrl uses NEXT_PUBLIC_API_URL and encodes query params", () => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000///";
    const url = buildUrl("/api/v1/sites", {
      siteId: "plasmodb",
      recordType: "gene",
      n: 2,
      ok: true,
      skip: null,
      missing: undefined,
    });
    expect(url).toBe(
      "http://localhost:8000/api/v1/sites?siteId=plasmodb&recordType=gene&n=2&ok=true",
    );
  });

  it("getAuthHeaders includes Bearer token and optional accept/content-type", () => {
    const headers = getAuthHeaders(undefined, {
      accept: "application/json",
      contentType: "application/json",
      extra: { "x-test": "1" },
    });
    expect(headers.Authorization).toBe("Bearer test-token");
    expect(headers.Accept).toBe("application/json");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["x-test"]).toBe("1");
  });

  it("requestJson returns parsed JSON on success", async () => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        makeResponse({
          ok: true,
          status: 200,
          statusText: "OK",
          headers: { "content-type": "application/json" },
          json: { hello: "world" },
        }),
      ),
    );

    const data = await requestJson<{ hello: string }>("/api/v1/health");
    expect(data).toEqual({ hello: "world" });
  });

  it("requestJson throws APIError with server 'detail' message", async () => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        makeResponse({
          ok: false,
          status: 401,
          statusText: "Unauthorized",
          headers: { "content-type": "application/json" },
          json: { detail: "No auth" },
        }),
      ),
    );

    await expect(requestJson("/api/v1/private")).rejects.toMatchObject({
      name: "APIError",
      message: "No auth",
      status: 401,
    });
  });

  it("requestJson throws APIError with generic message when no JSON detail", async () => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        makeResponse({
          ok: false,
          status: 500,
          statusText: "Internal Server Error",
          headers: { "content-type": "text/plain" },
          text: "nope",
        }),
      ),
    );

    try {
      await requestJson("/api/v1/broken");
      expect.unreachable();
    } catch (e) {
      expect(e).toBeInstanceOf(APIError);
      expect((e as APIError).message).toBe("HTTP 500 Internal Server Error");
      expect((e as APIError).status).toBe(500);
      expect((e as APIError).url).toContain("/api/v1/broken");
    }
  });
});
