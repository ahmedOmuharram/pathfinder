import { test, expect } from "../fixtures/test";
import type { APIResponse } from "@playwright/test";

interface AstNode {
  id?: string;
  parameters?: Record<string, { type?: string; value?: unknown }> | null;
  primaryInput?: AstNode | null;
  secondaryInput?: AstNode | null;
  [k: string]: unknown;
}

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

async function textExpressionOf(resp: APIResponse, stepId: string): Promise<unknown> {
  expect(resp.ok()).toBeTruthy();
  const ast = (await resp.json()) as unknown;
  const node = findNode(ast, stepId);
  expect(node, `step ${stepId} present in AST`).not.toBeNull();
  return node?.parameters?.["text_expression"]?.value;
}

async function paramKeysOf(resp: APIResponse, stepId: string): Promise<string[]> {
  expect(resp.status()).toBe(200);
  const node = findNode((await resp.json()) as unknown, stepId);
  expect(node, `step ${stepId} present in AST`).not.toBeNull();
  return Object.keys(node?.parameters ?? {}).sort();
}

test.describe("Edit leaf param from UI", () => {
  test("changing text_expression persists to AST + re-syncs to WDK", async ({
    chatPage,
    graphPage,
    sitePicker,
    apiClient,
  }) => {
    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat("plasmodb");

    await chatPage.send(
      "Build a strategy for P. falciparum 3D7 kinases using InterPro PF00069 and GO terms.",
    );
    await chatPage.expectPlanningArtifact();
    await chatPage.approvePlan();
    await chatPage.expectVerificationFeedback();

    const conversationId = chatPage.lastStrategyId;
    expect(conversationId).toBeTruthy();
    const astUrl = `/api/v1/conversations/${conversationId as string}/ast`;

    // Precondition: the InterPro leaf searches for "kinase".
    expect(
      await textExpressionOf(await apiClient.get(astUrl), "interpro_kinases"),
    ).toBe("kinase");

    // Open the leaf editor and change the text expression.
    await graphPage.goToStrategy("plasmodb", conversationId as string);
    await graphPage.expectStrategyTopbar();
    await graphPage.expectNodeVisible("interpro_kinases");
    await graphPage.clickNode("interpro_kinases");
    await expect(graphPage.editorSheet).toBeVisible({ timeout: 20_000 });

    const textInput = graphPage.editorSheet.locator('input[name="text_expression"]');
    await expect(textInput).toBeVisible({ timeout: 15_000 });
    // With the coercion fix the string input shows the persisted value, not
    // "[object Object]".
    await expect(textInput).toHaveValue("kinase");

    // Multi-pick values must load too: the seeded organism tree had one
    // selection. The pre-fix bug rendered it as "0 of N selected" (the
    // MultiPickValue collapsed to ["[object Object]"]).
    await expect(graphPage.editorSheet.getByText(/0 of \d+ selected/)).toHaveCount(0);
    await expect(
      graphPage.editorSheet.getByText(/[1-9]\d* of \d+ selected/),
    ).toBeVisible({ timeout: 15_000 });

    await textInput.fill("phosphatase");

    // Deferred commit: the footer Save appears once there's a change.
    const save = graphPage.editorSheet.getByTestId("step-editor-save");
    await expect(save).toBeVisible({ timeout: 15_000 });
    await save.click();

    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );

    // The edited param must be persisted in the AST (and have round-tripped
    // through the real WDK search-config push without erroring the sync).
    await expect
      .poll(
        async () => textExpressionOf(await apiClient.get(astUrl), "interpro_kinases"),
        { timeout: 30_000 },
      )
      .toBe("phosphatase");

    expect(await paramKeysOf(await apiClient.get(astUrl), "interpro_kinases")).toEqual([
      "document_type",
      "text_expression",
      "text_fields",
      "text_search_organism",
    ]);
  });
});
