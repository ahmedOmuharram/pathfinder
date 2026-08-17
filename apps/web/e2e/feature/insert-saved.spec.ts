import { test, expect } from "../fixtures/test";
import type { APIRequestContext, APIResponse } from "@playwright/test";
import { loginWdkAccount, wdkAccountCreds } from "../fixtures/wdk-account";

interface AstNode {
  id?: string;
  searchName?: string | null;
  expandedStrategyId?: number | null;
  [k: string]: unknown;
}

function collect(value: unknown, out: AstNode[]): void {
  if (value === null || typeof value !== "object") return;
  const node = value as AstNode;
  if (typeof node.id === "string") out.push(node);
  for (const child of Object.values(node)) collect(child, out);
}

async function astNodes(resp: APIResponse): Promise<AstNode[]> {
  expect(resp.ok()).toBeTruthy();
  const out: AstNode[] = [];
  collect((await resp.json()) as unknown, out);
  return out;
}

interface ChatPageLike {
  goto: () => Promise<void>;
  newChat: (s: string) => Promise<void>;
  send: (s: string) => Promise<void>;
  expectVerificationFeedback: () => Promise<void>;
  expectAssistantMessage: (p: RegExp, o?: { timeout?: number }) => Promise<void>;
  expectIdle: (timeout?: number) => Promise<void>;
  lastStrategyId: string | null;
}

type SitePickerLike = { selectSite: (s: string) => Promise<void> };

async function buildInterpro(
  chatPage: ChatPageLike,
  sitePicker: SitePickerLike,
): Promise<string> {
  await chatPage.goto();
  await sitePicker.selectSite("plasmodb");
  await chatPage.newChat("plasmodb");
  await chatPage.send(
    "Build a strategy for P. falciparum 3D7 kinases using InterPro PF00069 and GO terms.",
  );
  await chatPage.expectVerificationFeedback();
  const id = chatPage.lastStrategyId;
  expect(id).toBeTruthy();
  return id as string;
}

async function buildPlasmo(
  chatPage: ChatPageLike,
  sitePicker: SitePickerLike,
): Promise<string> {
  await chatPage.goto();
  await sitePicker.selectSite("plasmodb");
  await chatPage.newChat("plasmodb");
  await chatPage.send("create delegation");
  await chatPage.expectAssistantMessage(/\[mock\]/i, { timeout: 60_000 });
  await chatPage.expectIdle();
  const id = chatPage.lastStrategyId;
  expect(id).toBeTruthy();
  return id as string;
}

async function wdkStrategyIdOf(
  apiClient: APIRequestContext,
  conversationId: string,
): Promise<number | null> {
  const resp = await apiClient.get(`/api/v1/conversations/${conversationId}`);
  expect(resp.ok()).toBeTruthy();
  return ((await resp.json()) as { wdkStrategyId: number | null }).wdkStrategyId;
}

test.describe("Insert saved sub-strategy", () => {
  test("returns a clean 404 / 422 on unloadable saved id and malformed body", async ({
    chatPage,
    sitePicker,
    apiClient,
  }) => {
    const targetConvId = await buildInterpro(chatPage, sitePicker);

    const notFound = await apiClient.post(
      `/api/v1/conversations/${targetConvId}/insert-saved`,
      {
        params: { siteId: "plasmodb" },
        data: {
          targetStepId: "interpro_kinases",
          savedWdkStrategyId: 999_999_999,
          operator: "UNION",
        },
      },
    );
    expect(notFound.status()).toBe(404);
    expect(notFound.headers()["content-type"]).toContain("application/problem+json");
    const body = (await notFound.json()) as { code: string; status: number };
    expect(body.code).toBe("STRATEGY_NOT_FOUND");
    expect(body.status).toBe(404);

    const malformed = await apiClient.post(
      `/api/v1/conversations/${targetConvId}/insert-saved`,
      {
        params: { siteId: "plasmodb" },
        data: { savedWdkStrategyId: 123, operator: "UNION" },
      },
    );
    expect(malformed.status()).toBe(422);
  });

  test("inserts a saved WDK strategy as an expanded combine input (real account)", async ({
    page,
    chatPage,
    sitePicker,
  }) => {
    const creds = wdkAccountCreds();
    test.skip(
      creds == null,
      "set WDK_TEST_EMAIL/WDK_TEST_PASSWORD to run real-account WDK tests",
    );
    test.setTimeout(180_000);

    const ctx = page.context().request;
    const csrf = { "X-Requested-With": "XMLHttpRequest" };
    await loginWdkAccount(ctx, creds as NonNullable<typeof creds>, "plasmodb");
    await page.reload();

    const created: string[] = [];
    try {
      const savedConvId = await buildPlasmo(chatPage, sitePicker);
      created.push(savedConvId);
      await expect
        .poll(() => wdkStrategyIdOf(ctx, savedConvId), { timeout: 60_000 })
        .toBeTruthy();
      const savedWdkStrategyId = await wdkStrategyIdOf(ctx, savedConvId);
      const marked = await ctx.patch(`/api/v1/conversations/${savedConvId}`, {
        data: { isSaved: true },
        headers: csrf,
      });
      expect(marked.ok()).toBeTruthy();

      const targetConvId = await buildInterpro(chatPage, sitePicker);
      created.push(targetConvId);
      await expect
        .poll(() => wdkStrategyIdOf(ctx, targetConvId), { timeout: 60_000 })
        .toBeTruthy();
      const before = (
        await astNodes(await ctx.get(`/api/v1/conversations/${targetConvId}/ast`))
      ).length;

      const inserted = await ctx.post(
        `/api/v1/conversations/${targetConvId}/insert-saved`,
        {
          params: { siteId: "plasmodb" },
          data: {
            targetStepId: "interpro_kinases",
            savedWdkStrategyId: savedWdkStrategyId as number,
            operator: "UNION",
          },
          headers: csrf,
        },
      );
      expect(
        inserted.ok(),
        `insert ${inserted.status()}: ${await inserted.text()}`,
      ).toBeTruthy();
      const result = (await inserted.json()) as {
        insertedSavedWdkStrategyId: number;
        combineStepId: string;
        wdkStrategyId: number;
      };
      expect(result.insertedSavedWdkStrategyId).toBe(savedWdkStrategyId);
      expect(result.combineStepId).toBeTruthy();
      expect(typeof result.wdkStrategyId).toBe("number");

      const after = await astNodes(
        await ctx.get(`/api/v1/conversations/${targetConvId}/ast`),
      );
      expect(after.length).toBeGreaterThan(before);
      const expandedRefs = after
        .filter((n) => n.searchName === "__combine__")
        .map((n) => n.expandedStrategyId)
        .filter((v): v is number => v != null);
      expect(expandedRefs).toContain(savedWdkStrategyId);
    } finally {
      for (const id of created) {
        await ctx
          .delete(`/api/v1/conversations/${id}`, {
            params: { deleteFromWdk: "true" },
            headers: csrf,
          })
          .catch(() => undefined);
      }
    }
  });
});
