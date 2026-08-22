import { test, expect } from "../fixtures/test";
import { leafBySearch, leafIdBySearch } from "../fixtures/ast";

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
    await chatPage.expectVerificationFeedback();

    const conversationId = chatPage.lastStrategyId;
    expect(conversationId).toBeTruthy();
    const astUrl = `/api/v1/conversations/${conversationId as string}/ast`;

    // Precondition: the text leaf searches for "kinase".
    const leaf = await leafBySearch(await apiClient.get(astUrl), "GenesByText");
    expect(leaf.parameters?.["text_expression"]?.value).toBe("kinase");
    const leafId = leaf.id as string;

    // Open the leaf editor and change the text expression.
    await graphPage.goToStrategy("plasmodb", conversationId as string);
    await graphPage.expectStrategyTopbar();
    await graphPage.expectNodeVisible(leafId);
    await graphPage.clickNode(leafId);
    await expect(graphPage.editorSheet).toBeVisible({ timeout: 20_000 });

    const textInput = graphPage.editorSheet.locator('input[name="text_expression"]');
    await expect(textInput).toBeVisible({ timeout: 15_000 });
    // With the coercion fix the string input shows the persisted value, not
    // "[object Object]".
    await expect(textInput).toHaveValue("kinase");

    // Multi-pick values must load too: the organism tree had one selection. The
    // pre-fix bug rendered it as "0 of N selected" (the MultiPickValue collapsed
    // to ["[object Object]"]).
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
        async () =>
          (await leafBySearch(await apiClient.get(astUrl), "GenesByText")).parameters?.[
            "text_expression"
          ]?.value,
        { timeout: 30_000 },
      )
      .toBe("phosphatase");

    // The leaf keeps its identity and its whole parameter set across the edit.
    expect(await leafIdBySearch(await apiClient.get(astUrl), "GenesByText")).toBe(
      leafId,
    );
    const edited = await leafBySearch(await apiClient.get(astUrl), "GenesByText");
    expect(Object.keys(edited.parameters ?? {}).sort()).toEqual([
      "document_type",
      "text_expression",
      "text_fields",
      "text_search_organism",
    ]);
  });
});
