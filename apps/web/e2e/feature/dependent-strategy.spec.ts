import { test, expect } from "../fixtures/test";
import type { APIResponse } from "@playwright/test";

interface AstNode {
  id?: string;
  searchName?: string | null;
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

async function goLeaf(resp: APIResponse): Promise<AstNode> {
  expect(resp.status()).toBe(200);
  const node = findNode((await resp.json()) as unknown, "go_kinases");
  expect(node, "go_kinases present in AST").not.toBeNull();
  return node as AstNode;
}

const GO_PARAMS = [
  "go_term",
  "go_term_evidence",
  "go_term_slim",
  "go_typeahead",
  "organism",
];

test.describe("Dependent-param strategy (GenesByGoTerm)", () => {
  test("builds via chat, edits a param in the UI, re-syncs to WDK, model answers", async ({
    chatPage,
    graphPage,
    sitePicker,
    apiClient,
  }) => {
    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat("plasmodb");

    await chatPage.send("build a GO term strategy for protein kinase GO genes");
    await chatPage.expectPlanningArtifact();
    await chatPage.approvePlan();
    await chatPage.expectAssistantMessage(/\[mock\]/i, { timeout: 60_000 });
    await chatPage.expectIdle();

    const conversationId = chatPage.lastStrategyId as string;
    const astUrl = `/api/v1/conversations/${conversationId}/ast`;

    const built = await goLeaf(await apiClient.get(astUrl));
    expect(built.searchName).toBe("GenesByGoTerm");
    expect(Object.keys(built.parameters ?? {}).sort()).toEqual(GO_PARAMS);
    expect(built.parameters?.["go_term"]?.value).toBe("GO:0004672");

    await chatPage.send("what genes does this GO term strategy return?");
    await chatPage.expectAssistantMessage(/\[mock\]/i, { timeout: 60_000 });
    await chatPage.expectIdle();

    await graphPage.goToStrategy("plasmodb", conversationId);
    await graphPage.expectStrategyTopbar();
    await graphPage.clickNode("go_kinases");
    await expect(graphPage.editorSheet).toBeVisible({ timeout: 20_000 });

    await expect(
      graphPage.editorSheet.getByText(/[1-9]\d* of \d+ selected/),
    ).toBeVisible({ timeout: 15_000 });

    const goTerm = graphPage.editorSheet.locator('input[name="go_term"]');
    await expect(goTerm).toHaveValue("GO:0004672");
    await goTerm.fill("GO:0016301");

    const save = graphPage.editorSheet.getByTestId("step-editor-save");
    await expect(save).toBeVisible({ timeout: 15_000 });
    await save.click();

    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );

    const edited = await goLeaf(await apiClient.get(astUrl));
    expect(edited.parameters?.["go_term"]?.value).toBe("GO:0016301");
    expect(Object.keys(edited.parameters ?? {}).sort()).toEqual(GO_PARAMS);
  });

  test("the editor's More actions menu is reachable (not covered by the close button)", async ({
    page,
    chatPage,
    graphPage,
    sitePicker,
  }) => {
    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat("plasmodb");

    await chatPage.send("build a GO term strategy for protein kinase GO genes");
    await chatPage.expectPlanningArtifact();
    await chatPage.approvePlan();
    await chatPage.expectAssistantMessage(/\[mock\]/i, { timeout: 60_000 });
    await chatPage.expectIdle();

    await graphPage.goToStrategy("plasmodb", chatPage.lastStrategyId as string);
    await graphPage.clickNode("go_kinases");
    await expect(graphPage.editorSheet).toBeVisible({ timeout: 20_000 });

    await graphPage.editorSheet
      .getByRole("button", { name: "More actions" })
      .click({ timeout: 10_000 });
    await expect(page.getByRole("menuitem", { name: "Delete step" })).toBeVisible({
      timeout: 5_000,
    });
  });
});
