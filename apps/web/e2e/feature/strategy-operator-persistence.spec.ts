import { test, expect } from "../fixtures/test";
import type { APIResponse } from "@playwright/test";

interface AstNode {
  id?: string;
  operator?: string | null;
  primaryInput?: AstNode | null;
  secondaryInput?: AstNode | null;
  [k: string]: unknown;
}

/** Recursively locate a step node by id anywhere in the AST payload. */
function findNode(value: unknown, stepId: string): AstNode | null {
  if (value === null || typeof value !== "object") return null;
  const node = value as AstNode;
  if (node.id === stepId) return node;
  for (const child of Object.values(node)) {
    const hit = findNode(child, stepId);
    if (hit !== null) return hit;
  }
  return null;
}

async function operatorOf(
  resp: APIResponse,
  stepId: string,
): Promise<string | null | undefined> {
  expect(resp.ok()).toBeTruthy();
  const ast = (await resp.json()) as unknown;
  const node = findNode(ast, stepId);
  expect(node, `step ${stepId} present in AST`).not.toBeNull();
  return node?.operator;
}

test.describe("Operator change persists to AST", () => {
  test("UI flip UNION→INTERSECT lands in the persisted AST", async ({
    chatPage,
    graphPage,
    sitePicker,
    apiClient,
  }) => {
    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat("plasmodb");

    // One planning round → INTERPRO_SPEC (2 leaves + interpro_or_go UNION).
    await chatPage.send(
      "Build a strategy for P. falciparum 3D7 kinases using InterPro PF00069 and GO terms.",
    );
    await chatPage.expectPlanningArtifact();
    await chatPage.approvePlan();
    await chatPage.expectVerificationFeedback();

    const conversationId = chatPage.lastStrategyId;
    expect(conversationId).toBeTruthy();
    const astUrl = `/api/v1/conversations/${conversationId as string}/ast`;

    // Precondition: the combine starts as UNION in the persisted AST.
    expect(await operatorOf(await apiClient.get(astUrl), "interpro_or_go")).toBe(
      "UNION",
    );

    // UI mutation: flip the operator via the edge context menu.
    await graphPage.goToStrategy("plasmodb", conversationId as string);
    await graphPage.expectStrategyTopbar();
    await graphPage.expectNodeVisible("interpro_or_go");
    await graphPage.changeOperator("interpro_or_go", "INTERSECT");
    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );

    // The persisted AST must now carry INTERSECT — the assertion the
    // flagship journey is missing.
    await expect
      .poll(async () => operatorOf(await apiClient.get(astUrl), "interpro_or_go"), {
        timeout: 30_000,
      })
      .toBe("INTERSECT");
  });
});
