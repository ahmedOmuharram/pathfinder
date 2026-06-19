import { test, expect } from "../fixtures/test";
import type { APIResponse } from "@playwright/test";

interface AstNode {
  id?: string;
  searchName?: string | null;
  operator?: string | null;
  primaryInput?: AstNode | null;
  secondaryInput?: AstNode | null;
  [k: string]: unknown;
}

function collect(value: unknown, out: AstNode[]): void {
  if (value === null || typeof value !== "object") return;
  const node = value as AstNode;
  if (typeof node.id === "string") out.push(node);
  for (const child of Object.values(node)) collect(child, out);
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function astNodes(resp: APIResponse): Promise<AstNode[]> {
  expect(resp.status()).toBe(200);
  const out: AstNode[] = [];
  collect((await resp.json()) as unknown, out);
  return out;
}

test.describe("Execution phase (build strategy through the UI)", () => {
  test.beforeEach(async ({ chatPage, sitePicker }) => {
    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat("plasmodb");
  });

  test("single-leaf build materializes one GenesByTaxon step in the UI + AST", async ({
    chatPage,
    graphPage,
    apiClient,
  }) => {
    await chatPage.send("create delegation");
    await chatPage.expectPlanningArtifact();
    await chatPage.approvePlan();
    await chatPage.expectAssistantMessage(/\[mock\]/i, { timeout: 60_000 });
    await chatPage.expectIdle();

    const conversationId = chatPage.lastStrategyId as string;
    expect(conversationId).toMatch(UUID_RE);

    const nodes = await astNodes(
      await apiClient.get(`/api/v1/conversations/${conversationId}/ast`),
    );
    const searches = nodes.map((n) => n.searchName);
    expect(searches).toEqual(["GenesByTaxon"]);

    const conv = await apiClient.get(`/api/v1/conversations/${conversationId}`);
    expect((await conv.json()).wdkStrategyId).toBeGreaterThan(0);

    await graphPage.goToStrategy("plasmodb", conversationId);
    await graphPage.expectStrategyTopbar();
    await graphPage.expectNodeCount(1);
    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );
  });

  test("3-step combine build materializes both leaves + a UNION combine", async ({
    chatPage,
    graphPage,
    apiClient,
  }) => {
    await chatPage.send(
      "Build a strategy for P. falciparum 3D7 kinases using InterPro PF00069 and GO terms.",
    );
    await chatPage.expectPlanningArtifact();
    await chatPage.approvePlan();
    await chatPage.expectVerificationFeedback();

    const conversationId = chatPage.lastStrategyId as string;
    expect(conversationId).toMatch(UUID_RE);
    const nodes = await astNodes(
      await apiClient.get(`/api/v1/conversations/${conversationId}/ast`),
    );
    expect(nodes.map((n) => n.id).sort()).toEqual([
      "ec_kinases",
      "interpro_kinases",
      "interpro_or_go",
    ]);
    const combine = nodes.find((n) => n.id === "interpro_or_go");
    expect(combine?.operator).toBe("UNION");

    await graphPage.goToStrategy("plasmodb", conversationId);
    await graphPage.expectStrategyTopbar();
    await graphPage.expectNodeCount(3);
    await graphPage.expectNodeVisible("interpro_kinases");
    await graphPage.expectNodeVisible("ec_kinases");
    await graphPage.expectNodeVisible("interpro_or_go");
    await expect(graphPage.strategyPageStepCount).toContainText("3");
    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );
  });

  test("denying the plan builds nothing (no execution)", async ({
    chatPage,
    apiClient,
  }) => {
    const conversationId = chatPage.lastStrategyId as string;
    expect(conversationId).toMatch(UUID_RE);
    await chatPage.send(
      "Build a strategy for P. falciparum 3D7 kinases using InterPro PF00069 and GO terms.",
    );
    await chatPage.expectPlanningArtifact();
    await chatPage.denyPlan();
    await chatPage.expectIdle();

    const conv = await apiClient.get(`/api/v1/conversations/${conversationId}`);
    expect((await conv.json()).wdkStrategyId).toBeNull();
    const ast = await apiClient.get(`/api/v1/conversations/${conversationId}/ast`);
    expect(ast.status()).toBe(404);
  });
});
