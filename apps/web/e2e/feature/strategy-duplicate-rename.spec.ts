import { test, expect } from "../fixtures/test";
import type { APIResponse } from "@playwright/test";

interface AstNode {
  id?: string;
  displayName?: string | null;
  operator?: string | null;
  searchName?: string | null;
  [k: string]: unknown;
}

function collect(value: unknown, out: AstNode[]): void {
  if (value === null || typeof value !== "object") return;
  const node = value as AstNode;
  if (typeof node.id === "string") out.push(node);
  for (const child of Object.values(node)) collect(child, out);
}

async function nodes(resp: APIResponse): Promise<AstNode[]> {
  expect(resp.ok()).toBeTruthy();
  const out: AstNode[] = [];
  collect((await resp.json()) as unknown, out);
  return out;
}

async function buildInterpro(
  chatPage: {
    goto: () => Promise<void>;
    newChat: (s: string) => Promise<void>;
    send: (s: string) => Promise<void>;
    expectPlanningArtifact: () => Promise<void>;
    approvePlan: () => Promise<void>;
    expectVerificationFeedback: () => Promise<void>;
    lastStrategyId: string | null;
  },
  sitePicker: { selectSite: (s: string) => Promise<void> },
): Promise<string> {
  await chatPage.goto();
  await sitePicker.selectSite("plasmodb");
  await chatPage.newChat("plasmodb");
  await chatPage.send(
    "Build a strategy for P. falciparum 3D7 kinases using InterPro PF00069 and GO terms.",
  );
  await chatPage.expectPlanningArtifact();
  await chatPage.approvePlan();
  await chatPage.expectVerificationFeedback();
  const id = chatPage.lastStrategyId;
  expect(id).toBeTruthy();
  return id as string;
}

test.describe("Duplicate + rename step from UI", () => {
  test("duplicating a leaf via the node kebab adds steps to the AST", async ({
    page,
    chatPage,
    graphPage,
    sitePicker,
    apiClient,
  }) => {
    const conversationId = await buildInterpro(chatPage, sitePicker);
    const astUrl = `/api/v1/conversations/${conversationId}/ast`;

    const before = (await nodes(await apiClient.get(astUrl))).length;
    expect(before).toBe(3);

    await graphPage.goToStrategy("plasmodb", conversationId);
    await graphPage.expectStrategyTopbar();
    await graphPage.expectNodeVisible("interpro_kinases");

    await page.getByTestId("rf-node-interpro_kinases").hover();
    await page.getByTestId("rf-more-interpro_kinases").click();
    await page.getByRole("menuitem", { name: /duplicate step/i }).click();

    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 45_000 },
    );

    await expect
      .poll(async () => (await nodes(await apiClient.get(astUrl))).length, {
        timeout: 30_000,
      })
      .toBe(5);

    const all = await nodes(await apiClient.get(astUrl));
    const operators = all
      .filter((n) => n.searchName === "__combine__")
      .map((n) => n.operator)
      .sort();
    expect(operators).toEqual(["INTERSECT", "UNION"]);
    expect(all.map((n) => n.id)).toContain("interpro_kinases");
  });

  test("renaming a leaf via the editor persists displayName to the AST", async ({
    chatPage,
    graphPage,
    sitePicker,
    apiClient,
  }) => {
    const conversationId = await buildInterpro(chatPage, sitePicker);
    const astUrl = `/api/v1/conversations/${conversationId}/ast`;

    await graphPage.goToStrategy("plasmodb", conversationId);
    await graphPage.expectStrategyTopbar();
    await graphPage.expectNodeVisible("interpro_kinases");

    await graphPage.clickNode("interpro_kinases");
    await expect(graphPage.editorSheet).toBeVisible({ timeout: 20_000 });
    const nameInput = graphPage.editorStepNameInput;
    await nameInput.fill("Renamed kinase leaf");
    await nameInput.press("Enter");

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
        async () => {
          const all = await nodes(await apiClient.get(astUrl));
          return all.find((n) => n.id === "interpro_kinases")?.displayName;
        },
        { timeout: 30_000 },
      )
      .toBe("Renamed kinase leaf");
  });
});
