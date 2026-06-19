import { test, expect } from "../fixtures/test";

interface OpenResponse {
  conversationId?: string;
  strategyId?: string;
  id?: string;
}

test.describe("Open conversation", () => {
  test("POST /open with a siteId creates a retrievable conversation", async ({
    apiClient,
  }) => {
    const opened = await apiClient.post("/api/v1/conversations/open", {
      data: { siteId: "plasmodb" },
    });
    expect(opened.ok()).toBeTruthy();
    const body = (await opened.json()) as OpenResponse;
    const id = body.conversationId ?? body.strategyId ?? body.id;
    expect(id, "open returned a conversation id").toBeTruthy();
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
    );

    const got = await apiClient.get(`/api/v1/conversations/${id as string}`);
    expect(got.status()).toBe(200);
    const conv = (await got.json()) as { id: string; siteId: string };
    expect(conv.id).toBe(id);
    expect(conv.siteId).toBe("plasmodb");
  });
});
