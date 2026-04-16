/**
 * @vitest-environment jsdom
 */
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { ApiError, client } from "./client";

const BASE = "http://localhost:3000";

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("lib/api/client", () => {
  it("returns parsed JSON for GET", async () => {
    server.use(
      http.get(`${BASE}/api/v1/hello`, () =>
        HttpResponse.json({ greeting: "hi" }),
      ),
    );
    const result = await client<{ greeting: string }>({
      method: "get",
      url: "/api/v1/hello",
    });
    expect(result.status).toBe(200);
    expect(result.data).toEqual({ greeting: "hi" });
  });

  it("sends content-type application/json on POST with body", async () => {
    let seenContentType: string | null = null;
    let seenBody: unknown = null;
    server.use(
      http.post(`${BASE}/api/v1/echo`, async ({ request }) => {
        seenContentType = request.headers.get("content-type");
        seenBody = await request.json();
        return HttpResponse.json({ ok: true });
      }),
    );
    await client({
      method: "post",
      url: "/api/v1/echo",
      data: { x: 1 },
    });
    expect(seenContentType).toBe("application/json");
    expect(seenBody).toEqual({ x: 1 });
  });

  it("throws ApiError with status and parsed body on 4xx", async () => {
    server.use(
      http.get(`${BASE}/api/v1/nope`, () =>
        HttpResponse.json({ detail: "bad request" }, { status: 400 }),
      ),
    );
    await expect(
      client({ method: "get", url: "/api/v1/nope" }),
    ).rejects.toBeInstanceOf(ApiError);
    try {
      await client({ method: "get", url: "/api/v1/nope" });
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(400);
      expect(apiErr.data).toEqual({ detail: "bad request" });
    }
  });

  it("serializes query params and skips undefined values", async () => {
    let seenUrl: string | null = null;
    server.use(
      http.get(`${BASE}/api/v1/search`, ({ request }) => {
        seenUrl = request.url;
        return HttpResponse.json([]);
      }),
    );
    await client({
      method: "get",
      url: "/api/v1/search",
      params: { q: "malaria", limit: 10, skip: undefined, active: true },
    });
    expect(seenUrl).toContain("q=malaria");
    expect(seenUrl).toContain("limit=10");
    expect(seenUrl).toContain("active=true");
    expect(seenUrl).not.toContain("skip=");
  });
});
