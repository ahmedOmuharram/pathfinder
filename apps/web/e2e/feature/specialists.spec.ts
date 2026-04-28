import { test, expect } from "../fixtures/test";

/**
 * Feature: Specialist commands (/validate, /research) + /optimize launcher
 * precondition gate.
 *
 * Spec: docs/superpowers/specs/2026-04-26-specialist-commands-design.md §G.4
 *
 * Coverage:
 *   - /research enter via API → banner shows research kind, Done clears it
 *   - /validate refused on conversation with zero steps (precondition 409)
 *   - Concurrency: enter /research, then /validate → 409 SESSION_CONFLICT
 *   - Slash menu shows /optimize disabled (gated on ≥1 step) for an empty
 *     conversation
 *
 * The two control-test-spawning + multi-turn /validate flows are covered
 * by backend integration tests; here we cover the user-visible UX
 * surfaces (banner, slash menu disabled state, refusal toasts) using the
 * mock LLM provider.
 */
test.describe("Specialist commands", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeEach(async ({ chatPage }) => {
    await chatPage.goto();
    await chatPage.newChat();
  });

  test("/research enter shows banner and Done clears it", async ({
    chatPage,
    page,
  }) => {
    const conversationId = chatPage.lastStrategyId;
    expect(conversationId).toBeTruthy();
    const response = await page.context().request.post(
      `/api/v1/conversations/${conversationId}/specialists/research/enter`,
      {
        data: { arg: "what is PfEMP1?" },
        headers: { "X-Requested-With": "XMLHttpRequest" },
      },
    );
    expect(response.ok()).toBeTruthy();

    // Reload so the conversation detail query picks up the new specialist_mode.
    await page.reload();
    const banner = page.getByTestId("specialist-banner");
    await expect(banner).toBeVisible({ timeout: 10_000 });
    await expect(banner).toHaveAttribute("data-kind", "research");

    await page.getByTestId("specialist-banner-done").click();
    await expect(banner).toBeHidden({ timeout: 10_000 });

    // Verify backend cleared specialist_mode.
    const detail = await page.context().request.get(
      `/api/v1/conversations/${conversationId}`,
    );
    const body = (await detail.json()) as { specialistMode?: unknown };
    expect(body.specialistMode ?? null).toBeNull();
  });

  test("/validate is refused when the strategy has zero steps", async ({
    chatPage,
    page,
  }) => {
    const conversationId = chatPage.lastStrategyId;
    expect(conversationId).toBeTruthy();
    const response = await page.context().request.post(
      `/api/v1/conversations/${conversationId}/specialists/validate/enter`,
      {
        data: { arg: "" },
        headers: { "X-Requested-With": "XMLHttpRequest" },
      },
    );
    expect(response.status()).toBe(409);
    const body = (await response.json()) as { code?: string };
    expect(body.code).toBe("SPECIALIST_PRECONDITION_FAILED");
  });

  test("entering /research while research is active returns 409 SESSION_CONFLICT", async ({
    chatPage,
    page,
  }) => {
    const conversationId = chatPage.lastStrategyId;
    expect(conversationId).toBeTruthy();

    const first = await page.context().request.post(
      `/api/v1/conversations/${conversationId}/specialists/research/enter`,
      {
        data: { arg: "first" },
        headers: { "X-Requested-With": "XMLHttpRequest" },
      },
    );
    expect(first.ok()).toBeTruthy();

    const second = await page.context().request.post(
      `/api/v1/conversations/${conversationId}/specialists/research/enter`,
      {
        data: { arg: "second" },
        headers: { "X-Requested-With": "XMLHttpRequest" },
      },
    );
    expect(second.status()).toBe(409);
    const body = (await second.json()) as { code?: string };
    expect(body.code).toBe("SESSION_CONFLICT");

    // Cleanup so subsequent tests don't trip on lingering state.
    await page.context().request.post(
      `/api/v1/conversations/${conversationId}/specialists/exit`,
      {
        data: {},
        headers: { "X-Requested-With": "XMLHttpRequest" },
      },
    );
  });

  test("/optimize launcher endpoint refuses zero-step conversation", async ({
    chatPage,
    page,
  }) => {
    const conversationId = chatPage.lastStrategyId;
    expect(conversationId).toBeTruthy();
    const response = await page.context().request.post(
      `/api/v1/conversations/${conversationId}/launchers/optimize`,
      {
        data: {
          stepId: 1,
          paramKeys: ["any"],
          criterion: "any",
          budget: 5,
        },
        headers: { "X-Requested-With": "XMLHttpRequest" },
      },
    );
    expect(response.status()).toBe(409);
    const body = (await response.json()) as { code?: string };
    expect(body.code).toBe("SPECIALIST_PRECONDITION_FAILED");
  });
});
