/**
 * Journey 2: the tab and the thread co-edit one analysis.
 *
 * A filter applied in the subset cell travels as bind then set-filters, and the
 * next turn's analysis-state part states the same subset in the thread.
 */

import type { BrowserContext, Page } from "@playwright/test";

import { test, expect, BASE_URL } from "../fixtures/test";
import { sseDone, sseFrame, uiMessageStreamHeaders } from "../fixtures/sse";
import { CSRF_HEADERS } from "../fixtures/api-client";
import {
  analysisState,
  COUNTS_FEBRILE,
  DATASET_ID,
  edaJson,
  FEBRILE_FILTER,
  FEBRILE_SUMMARY,
  FILTERED_ANALYSIS,
  routeEdaReads,
  SAMPLE_ENTITY,
  SITE_ID,
  TEMPERATURE_VAR,
} from "../fixtures/eda";

async function openConversation(context: BrowserContext): Promise<string> {
  const response = await context.request.post(`${BASE_URL}/api/v1/conversations/open`, {
    data: { siteId: SITE_ID },
    headers: CSRF_HEADERS,
  });
  if (!response.ok()) throw new Error(`open failed: ${response.status()}`);
  const body = (await response.json()) as { conversationId?: string; id?: string };
  const id = body.conversationId ?? body.id;
  if (id === undefined || id === "") throw new Error("open returned no id");
  return id;
}

/** Answer the conversation binding: GET reports no analysis, and every PATCH
 * records its action and echoes the analysis that action produces. */
async function routeBinding(
  page: Page,
  conversationId: string,
  actions: string[],
): Promise<void> {
  await page.route(`**/api/v1/conversations/${conversationId}/eda`, async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill(edaJson({ analysis: null, descriptor: null }));
      return;
    }
    const body = route.request().postDataJSON() as { action: string };
    actions.push(body.action);
    const analysis = body.action === "bind" ? analysisState() : FILTERED_ANALYSIS;
    await route.fulfill(edaJson({ analysis, job: null, step: null }));
  });
}

test.describe("EDA tab and chat co-edit one analysis", () => {
  test("a filter added in the tab reaches the next analysis-state card", async ({
    page,
    context,
  }) => {
    const conversationId = await openConversation(context);
    await routeEdaReads(page);
    const actions: string[] = [];
    await routeBinding(page, conversationId, actions);

    await page.goto(`/${SITE_ID}/conversation/${conversationId}/eda`);

    await page.getByTestId("eda-study-search").fill("heat shock");
    await page.getByTestId(`eda-study-row-${DATASET_ID}`).click();
    await expect(page.getByTestId("eda-subset-cell")).toBeVisible({ timeout: 20_000 });
    // The bind echo carries the unfiltered counts: 12 of 12 samples.
    await expect(page.getByTestId(`eda-entity-${SAMPLE_ENTITY}`)).toContainText(
      "12 of 12",
    );

    await page.getByTestId(`eda-variable-${TEMPERATURE_VAR}`).click();
    await page.getByRole("checkbox", { name: "febrile" }).check();
    await page.getByRole("button", { name: "Apply filter" }).click();

    // The live count for the febrile subset: half of the 12 samples.
    await expect(page.getByTestId(`eda-entity-${SAMPLE_ENTITY}`)).toContainText(
      "6 of 12",
    );
    await expect(
      page.getByTestId(`eda-filter-chip-${SAMPLE_ENTITY}-${TEMPERATURE_VAR}`),
    ).toContainText("febrile");
    expect(actions).toEqual(["bind", "set-filters"]);

    // The next turn re-states the same analysis, and the thread agrees.
    const stream = [
      sseFrame({
        type: "start",
        messageId: "44444444-4444-4444-4444-444444444444",
        messageMetadata: {
          phase: "frame",
          model: "mock:deterministic",
          traceId: "mock-eda-coedit",
          createdAt: new Date().toISOString(),
        },
      }),
      sseFrame({
        type: "data-eda.analysis-state",
        data: analysisState({
          revision: 2,
          numFilters: 1,
          filters: [FEBRILE_FILTER],
          filterSummaries: [FEBRILE_SUMMARY],
          entityCounts: COUNTS_FEBRILE,
        }),
      }),
      sseFrame({ type: "finish", finishReason: "stop" }),
      sseDone(),
    ].join("");
    await page.route("**/api/v1/chat", (route) =>
      route.fulfill({ status: 200, headers: uiMessageStreamHeaders(), body: stream }),
    );

    await page.goto(`/${SITE_ID}/conversation/${conversationId}`);
    const composer = page.getByTestId("message-input");
    await expect(composer).toBeVisible({ timeout: 30_000 });
    await composer.click();
    await composer.pressSequentially("what is in the subset now", { delay: 15 });
    await expect(page.getByRole("button", { name: /Send/i })).toBeEnabled({
      timeout: 15_000,
    });
    await composer.press("Enter");

    await expect(page.getByTestId("data-eda-filter-chip-0")).toContainText(
      FEBRILE_SUMMARY,
      { timeout: 20_000 },
    );
    await expect(page.getByTestId("data-eda-analysis-state")).toContainText(
      "6 of 12 Sample",
    );
  });
});
