import { test, expect } from "../fixtures/test";
import { leafBySearch, leafIdBySearch } from "../fixtures/ast";

const GO_PARAMS = [
  "go_term",
  "go_term_evidence",
  "go_term_slim",
  "go_typeahead",
  "organism",
];

const GO_PROMPT = "build a GO term strategy for protein kinase GO genes";

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

    await chatPage.send(GO_PROMPT);
    await chatPage.expectVerificationSuccess();
    await chatPage.expectIdle();

    const conversationId = chatPage.lastStrategyId as string;
    const astUrl = `/api/v1/conversations/${conversationId}/ast`;

    // The frame binds the criterion through go_typeahead (the vocabulary
    // half); go_term stays at its "N/A" default.
    const built = await leafBySearch(await apiClient.get(astUrl), "GenesByGoTerm");
    expect(Object.keys(built.parameters ?? {}).sort()).toEqual(GO_PARAMS);
    expect(built.parameters?.["go_typeahead"]?.values).toEqual(["GO:0004672"]);
    expect(built.parameters?.["go_term"]?.value).toBe("N/A");
    const leafId = built.id as string;

    // The question must not name the GO arc: a marker phrase routes the mock
    // into a rebuild, which re-mints every step id.
    await chatPage.send("what genes does this return?");
    await chatPage.expectIdle();

    await graphPage.goToStrategy("plasmodb", conversationId);
    await graphPage.expectStrategyTopbar();
    await graphPage.clickNode(leafId);
    await expect(graphPage.editorSheet).toBeVisible({ timeout: 20_000 });

    await expect(
      graphPage.editorSheet.getByText(/[1-9]\d* of \d+ selected/),
    ).toBeVisible({ timeout: 15_000 });

    const goTerm = graphPage.editorSheet.locator('input[name="go_term"]');
    await expect(goTerm).toHaveValue("N/A");
    await goTerm.fill("GO:0016301");

    const save = graphPage.editorSheet.getByTestId("step-editor-save");
    await expect(save).toBeVisible({ timeout: 15_000 });
    await save.click();

    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );

    // The dependent vocabulary re-reads under the new parent without dropping
    // any of the search's parameters.
    await expect
      .poll(
        async () =>
          (await leafBySearch(await apiClient.get(astUrl), "GenesByGoTerm"))
            .parameters?.["go_term"]?.value,
        { timeout: 30_000 },
      )
      .toBe("GO:0016301");
    const edited = await leafBySearch(await apiClient.get(astUrl), "GenesByGoTerm");
    expect(Object.keys(edited.parameters ?? {}).sort()).toEqual(GO_PARAMS);
    expect(edited.id).toBe(leafId);
  });

  test("the editor's More actions menu is reachable (not covered by the close button)", async ({
    page,
    chatPage,
    graphPage,
    sitePicker,
    apiClient,
  }) => {
    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat("plasmodb");

    await chatPage.send(GO_PROMPT);
    await chatPage.expectVerificationSuccess();
    await chatPage.expectIdle();

    const conversationId = chatPage.lastStrategyId as string;
    const leafId = await leafIdBySearch(
      await apiClient.get(`/api/v1/conversations/${conversationId}/ast`),
      "GenesByGoTerm",
    );

    await graphPage.goToStrategy("plasmodb", conversationId);
    await graphPage.clickNode(leafId);
    await expect(graphPage.editorSheet).toBeVisible({ timeout: 20_000 });

    await graphPage.editorSheet
      .getByRole("button", { name: "More actions" })
      .click({ timeout: 10_000 });
    await expect(page.getByRole("menuitem", { name: "Delete step" })).toBeVisible({
      timeout: 5_000,
    });
  });
});
