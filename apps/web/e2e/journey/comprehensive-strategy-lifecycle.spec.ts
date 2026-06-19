import { test, expect } from "../fixtures/test";
import type { APIResponse } from "@playwright/test";
import { wdkAccountCreds, loginWdkAccount } from "../fixtures/wdk-account";

interface ParamValue {
  value?: unknown;
  values?: unknown[];
}

interface AstNode {
  id?: string;
  searchName?: string | null;
  operator?: string | null;
  parameters?: Record<string, ParamValue> | null;
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

async function astById(resp: APIResponse): Promise<Record<string, AstNode>> {
  expect(resp.status()).toBe(200);
  const out: AstNode[] = [];
  collect((await resp.json()) as unknown, out);
  return Object.fromEntries(out.map((n) => [n.id as string, n]));
}

test.describe("Comprehensive multi-param strategy lifecycle", () => {
  test.use({ viewport: { width: 1680, height: 900 } });

  test("scoping → build 5-step all-param strategy → verify → optimize → edit every param type → operator flip → delete → Q&A", async ({
    page,
    chatPage,
    graphPage,
    sitePicker,
  }) => {
    const creds = wdkAccountCreds();
    test.skip(creds === null, "Requires WDK_TEST_EMAIL/WDK_TEST_PASSWORD");

    await loginWdkAccount(page.context().request, creds!, "plasmodb");

    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat("plasmodb");

    await chatPage.send(
      "I'm studying P. falciparum kinases — how strict on 'doesn't vary much' should I be?",
    );
    await chatPage.expectClarifyingQuestions();

    await chatPage.send(
      "Build a comprehensive kinase strategy with all parameter types.",
    );
    await chatPage.expectPlanningArtifact();
    await chatPage.approvePlan();
    await chatPage.expectVerificationSuccess();
    await chatPage.expectIdle();

    const conversationId = chatPage.lastStrategyId as string;
    const astUrl = `/api/v1/conversations/${conversationId}/ast`;

    const built = await astById(await page.request.get(astUrl));
    expect(Object.keys(built).sort()).toEqual([
      "go_kinase_genes",
      "narrowed",
      "pf_taxon",
      "text_kinases",
      "text_or_go",
    ]);
    expect(built["text_kinases"]?.searchName).toBe("GenesByText");
    expect(built["go_kinase_genes"]?.searchName).toBe("GenesByGoTerm");
    expect(built["pf_taxon"]?.searchName).toBe("GenesByTaxon");
    expect(built["text_or_go"]?.operator).toBe("UNION");
    expect(built["narrowed"]?.operator).toBe("INTERSECT");
    expect(built["go_kinase_genes"]?.parameters?.["go_term_evidence"]?.values).toEqual([
      "Curated",
      "Computed",
    ]);

    await graphPage.goToStrategy("plasmodb", conversationId);
    await graphPage.expectStrategyTopbar();
    await graphPage.expectNodeCount(5);

    await graphPage.clickNode("text_kinases");
    await graphPage.expectEditorSheetOpen();
    const textInput = graphPage.editorSheet.locator('input[name="text_expression"]');
    await expect(textInput).toHaveValue("kinase");
    await textInput.fill("phosphatase");
    await graphPage.saveEditor();
    await expect
      .poll(
        async () =>
          (await astById(await page.request.get(astUrl)))["text_kinases"]?.parameters?.[
            "text_expression"
          ]?.value,
        { timeout: 30_000 },
      )
      .toBe("phosphatase");

    await graphPage.clickNode("go_kinase_genes");
    await graphPage.expectEditorSheetOpen();
    await graphPage.expandEditorAdvanced();
    await graphPage.toggleEditorCheckbox("Computed");
    await graphPage.saveEditor();
    await expect
      .poll(
        async () =>
          (await astById(await page.request.get(astUrl)))["go_kinase_genes"]
            ?.parameters?.["go_term_evidence"]?.values,
        { timeout: 30_000 },
      )
      .toEqual(["Curated"]);

    await graphPage.changeOperator("text_or_go", "INTERSECT");
    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );
    await expect
      .poll(
        async () =>
          (await astById(await page.request.get(astUrl)))["text_or_go"]?.operator,
        { timeout: 30_000 },
      )
      .toBe("INTERSECT");

    await graphPage.deleteStep("pf_taxon");
    await graphPage.expectNodeCount(3);
    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );
    await expect
      .poll(
        async () => Object.keys(await astById(await page.request.get(astUrl))).sort(),
        { timeout: 30_000 },
      )
      .toEqual(["go_kinase_genes", "text_kinases", "text_or_go"]);

    await page.goto(`/plasmodb/conversation/${conversationId}`);
    await graphPage.expectOnChatRoute(conversationId);
    await chatPage.send("Compare search variants for the text-kinase leaf.");
    await chatPage.expectVariantComparison();
    await chatPage.expectIdle();

    await chatPage.send("How many genes does this strategy return now?");
    await chatPage.expectAssistantMessage(/\[mock\]/i, { timeout: 90_000 });
    await chatPage.expectIdle();
  });
});
