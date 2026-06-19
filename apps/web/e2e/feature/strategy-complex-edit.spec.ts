import { test, expect } from "../fixtures/test";
import type { APIResponse } from "@playwright/test";

interface AstNode {
  id?: string;
  searchName?: string | null;
  operator?: string | null;
  parameters?: Record<string, { value?: unknown }> | null;
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

async function nodeOf(resp: APIResponse, stepId: string): Promise<AstNode> {
  expect(resp.status()).toBe(200);
  const node = findNode((await resp.json()) as unknown, stepId);
  expect(node, `${stepId} present in AST`).not.toBeNull();
  return node as AstNode;
}

test.describe("Complex combine strategy — multi-edit via UI", () => {
  test("build 3-step combine, flip operator + edit a leaf param, both persist + sync, model answers", async ({
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

    const conversationId = chatPage.lastStrategyId as string;
    const astUrl = `/api/v1/conversations/${conversationId}/ast`;

    const combine = await nodeOf(await apiClient.get(astUrl), "interpro_or_go");
    expect(combine.operator).toBe("UNION");
    const leaf = await nodeOf(await apiClient.get(astUrl), "interpro_kinases");
    expect(leaf.searchName).toBe("GenesByText");
    expect(leaf.parameters?.["text_expression"]?.value).toBe("kinase");

    await chatPage.send("how many genes are in this combined strategy?");
    await chatPage.expectAssistantMessage(/\[mock\]/i, { timeout: 60_000 });
    await chatPage.expectIdle();

    await graphPage.goToStrategy("plasmodb", conversationId);
    await graphPage.expectStrategyTopbar();

    await graphPage.changeOperator("interpro_or_go", "INTERSECT");
    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );
    await expect
      .poll(
        async () =>
          (await nodeOf(await apiClient.get(astUrl), "interpro_or_go")).operator,
        { timeout: 30_000 },
      )
      .toBe("INTERSECT");

    await graphPage.clickNode("interpro_kinases");
    await expect(graphPage.editorSheet).toBeVisible({ timeout: 20_000 });
    const textInput = graphPage.editorSheet.locator('input[name="text_expression"]');
    await expect(textInput).toHaveValue("kinase");
    await textInput.fill("phosphatase");
    const save = graphPage.editorSheet.getByTestId("step-editor-save");
    await expect(save).toBeVisible({ timeout: 15_000 });
    await save.click();
    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );

    await expect
      .poll(
        async () =>
          (await nodeOf(await apiClient.get(astUrl), "interpro_kinases")).parameters?.[
            "text_expression"
          ]?.value,
        { timeout: 30_000 },
      )
      .toBe("phosphatase");
    expect((await nodeOf(await apiClient.get(astUrl), "interpro_or_go")).operator).toBe(
      "INTERSECT",
    );
  });
});
