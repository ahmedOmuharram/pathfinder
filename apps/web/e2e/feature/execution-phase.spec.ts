import { test, expect } from "../fixtures/test";
import { COMBINE_SEARCH_NAME, astNodes, combineNode } from "../fixtures/ast";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

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
    await chatPage.expectVerificationSuccess();
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
    await chatPage.expectVerificationFeedback();

    const conversationId = chatPage.lastStrategyId as string;
    expect(conversationId).toMatch(UUID_RE);
    const astUrl = `/api/v1/conversations/${conversationId}/ast`;

    const nodes = await astNodes(await apiClient.get(astUrl));
    expect(nodes).toHaveLength(3);
    expect(nodes.map((n) => n.searchName).sort()).toEqual([
      "GenesByTaxon",
      "GenesByText",
      COMBINE_SEARCH_NAME,
    ]);
    const combine = await combineNode(await apiClient.get(astUrl));
    expect(combine.operator).toBe("UNION");
    // Both leaves feed the combine, rather than one hanging unattached.
    expect([combine.primaryInput?.id, combine.secondaryInput?.id].sort()).toEqual(
      nodes
        .filter((n) => n.searchName !== COMBINE_SEARCH_NAME)
        .map((n) => n.id)
        .sort(),
    );

    await graphPage.goToStrategy("plasmodb", conversationId);
    await graphPage.expectStrategyTopbar();
    await graphPage.expectNodeCount(3);
    for (const node of nodes) {
      await graphPage.expectNodeVisible(node.id as string);
    }
    await expect(graphPage.strategyPageStepCount).toContainText("3");
    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );
  });
});
