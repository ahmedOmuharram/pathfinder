import { test, expect } from "../fixtures/test";

test.describe("P. falciparum candidate drug-targets journey (7 turns)", () => {
  test("vague prompt → 16-node verified strategy → UI op-change impact", async ({
    chatPage,
    graphPage,
    sitePicker,
    apiClient,
  }) => {
    await chatPage.goto();
    await sitePicker.selectSite("plasmodb");
    await chatPage.newChat("plasmodb");

    // ── Turn 1: vague drug-target question ──────────────────────
    await chatPage.send(
      "I want to find candidate drug targets in Plasmodium — kinases that are expressed, don't vary much, and have no human equivalent.",
    );
    await chatPage.expectClarifyingQuestions();

    // ── Turn 2: user clarifies all four ─────────────────────────
    await chatPage.send(
      "Use P. falciparum 3D7. For 'expressed' use trophozoite-stage mass spec OR DeRisi microarray top 10%. For 'doesn't vary much' use dN/dS ≤ 1.3 on the Broad 3K SNP array. For 'no human equivalent' use the phylogenetic profile pattern %hsap:N%pfal:Y%.",
    );
    await chatPage.expectPlanningArtifact();

    // ── Turn 3: deny with feedback to add InterPro + EC ─────────
    await chatPage.denyPlan();
    await chatPage.send(
      "Add InterPro PF00069 (Pkinase) and EC 2.7.-.- to broaden kinase identification.",
    );
    await chatPage.expectPlanningArtifact();
    await expect(chatPage.lastPlanArtifact).toContainText(/InterPro|PF00069|EC/i, {
      timeout: 120_000,
    });

    // ── Turn 4: approve refined plan → execution → verification FAIL ──
    await chatPage.approvePlan();
    await chatPage.expectVerificationFeedback();

    // ── Turn 5: fix the phylogenetic pattern → verification SUCCESS ──
    await chatPage.send(
      "Fix the phylogenetic pattern by loosening to %MAMM:N%pfal:Y%.",
    );
    await chatPage.expectVerificationSuccess();

    // ── Turn 6: UI mutation — flip interpro_or_go operator ──────
    const conversationId = chatPage.lastStrategyId;
    expect(conversationId).toBeTruthy();
    await graphPage.goToStrategy("plasmodb", conversationId as string);
    await graphPage.expectStrategyTopbar();
    await graphPage.expectNodeVisible("interpro_or_go");
    await graphPage.changeOperator("interpro_or_go", "INTERSECT");
    await expect(graphPage.strategyPageSyncState).toHaveAttribute(
      "data-sync-state",
      "idle",
      { timeout: 30_000 },
    );
    await graphPage.strategyPageBackButton.click();
    await graphPage.expectOnChatRoute(conversationId as string);

    // ── Turn 7: ask for impact analysis ─────────────────────────
    await chatPage.send(
      "What's the impact of switching the InterPro/GO combine to INTERSECT?",
    );
    await chatPage.expectAssistantMessage(
      /impact|drops|stricter|operator/i,
      { timeout: 90_000 },
    );

    const resp = await apiClient.get(
      `/api/v1/conversations/${conversationId as string}`,
    );
    expect(resp.ok()).toBeTruthy();
  });
});
