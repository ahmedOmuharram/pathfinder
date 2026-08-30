/**
 * EDA acceptance journeys. Frozen; implementers may not edit this file.
 *
 * These run only when EDA_ACCEPTANCE is set:
 *   EDA_ACCEPTANCE=1 npx playwright test --project=eda-acceptance
 *
 * Every EDA route is answered from payloads embedded here, so the suite never
 * depends on an implementer's fixture file. The chat turn is route-mocked the
 * way e2e/feature/durable-verification.spec.ts mocks it.
 */

import { test, expect, BASE_URL } from "../fixtures/test";
import { sseDone, sseFrame, uiMessageStreamHeaders } from "../fixtures/sse";
import { CSRF_HEADERS } from "../fixtures/api-client";
import type { BrowserContext, Page } from "@playwright/test";

test.skip(
  () => process.env["EDA_ACCEPTANCE"] !== "1",
  "EDA acceptance journeys run explicitly, at batch 7 close",
);

const DATASET_ID = "DS_e973eadd57";
const SAMPLE_ENTITY = "ENT_8151325d";
const COUNTS_ENTITY = "ENT_fd574cd6";
const TEMPERATURE_VAR = "VAR_081ab087";
const STUDY_TITLE = "Heat shock response in sensitive mutants (LRR5, DHC)";

const STUDY_ROW = {
  datasetId: DATASET_ID,
  studyId: "STUDY_e973eadd57",
  displayName: STUDY_TITLE,
  shortDisplayName: "Heat shock",
  description: "Heat shock response in P. falciparum 3D7 sensitive mutants",
  sourceType: "curated",
  relevance: 1,
  canSubset: true,
  canExportRows: true,
};

/** The flat study detail the route serves: entities name their parent and
 * variables name their entity; the server has already derived filterType. */
const STUDY_DETAIL = {
  datasetId: DATASET_ID,
  studyId: "STUDY_e973eadd57",
  displayName: STUDY_TITLE,
  entities: [
    {
      entityId: SAMPLE_ENTITY,
      displayName: "Sample",
      displayNamePlural: "Samples",
      parentEntityId: null,
      variableCount: 1,
      hasGeneId: false,
    },
    {
      entityId: COUNTS_ENTITY,
      displayName: "pfal3D7 htseq counts",
      displayNamePlural: "pfal3D7 htseq counts",
      parentEntityId: SAMPLE_ENTITY,
      variableCount: 2,
      hasGeneId: true,
    },
  ],
  variables: [
    {
      entityId: SAMPLE_ENTITY,
      variableId: TEMPERATURE_VAR,
      displayName: "temperature_condition",
      variableType: "string",
      filterType: "stringSet",
      dataShape: "categorical",
      isMultiValued: false,
      vocabulary: ["febrile", "normal"],
      vocabularyTotal: 2,
      vocabularyNote: null,
      rangeMin: null,
      rangeMax: null,
      dateMin: null,
      dateMax: null,
      subFilterVariableIds: [],
      hideFrom: [],
    },
    {
      entityId: COUNTS_ENTITY,
      variableId: "VEUPATHDB_GENE_ID",
      displayName: "Gene ID",
      variableType: "string",
      filterType: "stringSet",
      dataShape: "categorical",
      isMultiValued: false,
      vocabulary: [],
      vocabularyTotal: 5720,
      vocabularyNote: "5720 values; the first 0 are listed",
      rangeMin: null,
      rangeMax: null,
      dateMin: null,
      dateMax: null,
      subFilterVariableIds: [],
      hideFrom: [],
    },
    {
      entityId: COUNTS_ENTITY,
      variableId: "SEQUENCE_READ_COUNT_SENSE",
      displayName: "Read count, sense",
      variableType: "integer",
      filterType: "numberRange",
      dataShape: "continuous",
      isMultiValued: false,
      vocabulary: [],
      vocabularyTotal: 0,
      vocabularyNote: null,
      rangeMin: 0,
      rangeMax: 68640,
      dateMin: null,
      dateMax: null,
      subFilterVariableIds: [],
      hideFrom: [],
    },
  ],
  geneEntityId: COUNTS_ENTITY,
  geneEntityProblem: null,
  canSubset: true,
  canExportRows: true,
};

const COUNTS_UNFILTERED = [
  {
    entityId: SAMPLE_ENTITY,
    entityDisplayName: "Sample",
    count: 12,
    unfilteredCount: 12,
  },
  {
    entityId: COUNTS_ENTITY,
    entityDisplayName: "pfal3D7 htseq counts",
    count: 68640,
    unfilteredCount: 68640,
  },
];

const COUNTS_FEBRILE = [
  {
    entityId: SAMPLE_ENTITY,
    entityDisplayName: "Sample",
    count: 6,
    unfilteredCount: 12,
  },
  {
    entityId: COUNTS_ENTITY,
    entityDisplayName: "pfal3D7 htseq counts",
    count: 34320,
    unfilteredCount: 68640,
  },
];

const FEBRILE_FILTER = {
  entityId: SAMPLE_ENTITY,
  variableId: TEMPERATURE_VAR,
  type: "stringSet",
  stringSet: ["febrile"],
};

const FEBRILE_DISTRIBUTION = {
  variableId: TEMPERATURE_VAR,
  variableDisplayName: "temperature_condition",
  labels: ["febrile"],
  values: [6],
  subsetSize: 6,
  numVarValues: 6,
  numMissingCases: 0,
  isMultiValued: false,
};

function analysisState(overrides: Record<string, unknown> = {}) {
  return {
    siteId: "plasmodb",
    datasetId: DATASET_ID,
    studyId: "STUDY_e973eadd57",
    analysisId: "a-acc-1",
    revision: 0,
    studyDisplayName: STUDY_TITLE,
    displayName: "Unsaved analysis",
    numFilters: 0,
    numComputations: 0,
    filters: [],
    filterSummaries: [],
    entityCounts: COUNTS_UNFILTERED,
    canExportRows: true,
    ...overrides,
  };
}

const FILTERED_ANALYSIS = analysisState({
  revision: 1,
  numFilters: 1,
  filters: [FEBRILE_FILTER],
  filterSummaries: ["temperature_condition is febrile"],
  entityCounts: COUNTS_FEBRILE,
});

/** One point per gene, with the live row that carries no p-value. */
const VOLCANO_VIZ = {
  datasetId: DATASET_ID,
  analysisId: "a-acc-1",
  chart: "volcano",
  effectSizeLabel: "log2(Fold Change)",
  effectSizeThreshold: 1,
  significanceThreshold: 0.05,
  effectDirection: "upAndDown",
  totalPoints: 3,
  retainedPoints: 1,
  points: [
    {
      pointId: "PF3D7_0100100",
      effectSize: -0.218035922112735,
      pValue: 0.350285751849808,
      adjustedPValue: 0.46960449943855,
      retained: false,
    },
    {
      pointId: "PF3D7_0100200",
      effectSize: 3.94437533216012,
      pValue: 1.95781599815607e-5,
      adjustedPValue: 0.000137772236907279,
      retained: true,
    },
    {
      pointId: "PF3D7_MIT04200",
      effectSize: -1.49447459261845,
      pValue: null,
      adjustedPValue: null,
      retained: false,
    },
  ],
};

const SUBSET_PREVIEW = {
  datasetId: DATASET_ID,
  analysisId: "a-acc-1",
  entityCounts: COUNTS_FEBRILE,
  distribution: FEBRILE_DISTRIBUTION,
};

const EXPORTED_STEP = {
  id: "step_eda_acc",
  searchName: "GenesByEdaVizWithCompute",
  displayName: "EDA volcano, 1543 genes",
  estimatedSize: 1543,
};

async function openConversation(context: BrowserContext): Promise<string> {
  const response = await context.request.post(`${BASE_URL}/api/v1/conversations/open`, {
    data: { siteId: "plasmodb" },
    headers: CSRF_HEADERS,
  });
  if (!response.ok()) throw new Error(`open failed: ${response.status()}`);
  const body = (await response.json()) as { conversationId?: string; id?: string };
  const id = body.conversationId ?? body.id;
  if (id === undefined || id === "") throw new Error("open returned no id");
  return id;
}

function json(body: unknown) {
  return { status: 200, contentType: "application/json", body: JSON.stringify(body) };
}

/** The study reads the tab makes. The detail pattern is registered last so it
 * wins over the search pattern on Playwright's last-registered-first order.
 * A count is one entity per request; the answer follows the request's filters. */
async function routeEdaReads(page: Page): Promise<void> {
  await page.route("**/api/v1/eda/count?*", (route) => {
    const body = route.request().postDataJSON() as {
      entityId: string;
      filters?: unknown[];
    };
    const table =
      (body.filters ?? []).length === 0 ? COUNTS_UNFILTERED : COUNTS_FEBRILE;
    const row = table.find((entry) => entry.entityId === body.entityId);
    if (row === undefined) throw new Error(`no count fixture for ${body.entityId}`);
    return route.fulfill(
      json({
        entityId: row.entityId,
        count: row.count,
        unfilteredCount: row.unfilteredCount,
      }),
    );
  });
  await page.route("**/api/v1/eda/distribution?*", (route) =>
    route.fulfill(json(FEBRILE_DISTRIBUTION)),
  );
  await page.route("**/api/v1/eda/studies?*", (route) =>
    route.fulfill(json({ studies: [STUDY_ROW] })),
  );
  await page.route(`**/api/v1/eda/studies/${DATASET_ID}*`, (route) =>
    route.fulfill(json(STUDY_DETAIL)),
  );
}

async function sendTurn(page: Page, text: string): Promise<void> {
  const composer = page.getByTestId("message-input");
  await expect(composer).toBeVisible({ timeout: 30_000 });
  await composer.click();
  await composer.pressSequentially(text, { delay: 15 });
  await expect(page.getByRole("button", { name: /Send/i })).toBeEnabled({
    timeout: 15_000,
  });
  await composer.press("Enter");
}

test.describe("EDA acceptance journeys", () => {
  test("chat draws the EDA cards and the tab opens on the same analysis", async ({
    page,
    context,
  }) => {
    const conversationId = await openConversation(context);
    await routeEdaReads(page);
    await page.route(`**/api/v1/conversations/${conversationId}/eda`, (route) =>
      route.fulfill(json({ analysis: FILTERED_ANALYSIS, descriptor: null })),
    );
    const stream = [
      sseFrame({
        type: "start",
        messageId: "aaaaaaaa-0000-4000-8000-00000000000a",
        messageMetadata: {
          phase: "frame",
          model: "mock:deterministic",
          traceId: "eda-acceptance-1",
          createdAt: new Date().toISOString(),
        },
      }),
      sseFrame({ type: "data-eda.analysis-state", data: FILTERED_ANALYSIS }),
      sseFrame({ type: "data-eda.subset-preview", data: SUBSET_PREVIEW }),
      sseFrame({ type: "data-eda.viz", data: VOLCANO_VIZ }),
      sseFrame({ type: "finish", finishReason: "stop" }),
      sseDone(),
    ].join("");
    await page.route("**/api/v1/chat", (route) =>
      route.fulfill({ status: 200, headers: uiMessageStreamHeaders(), body: stream }),
    );

    await page.goto(`/plasmodb/conversation/${conversationId}`);
    await sendTurn(page, "explore the heat shock study");

    const card = page.getByTestId("data-eda-analysis-state");
    await expect(card).toBeVisible({ timeout: 20_000 });
    await expect(card).toContainText(STUDY_TITLE);
    await expect(card).toContainText("6 of 12 Sample");
    await expect(page.getByTestId("data-eda-filter-chip-0")).toContainText(
      "temperature_condition is febrile",
    );
    await expect(page.getByTestId("data-eda-subset-preview")).toContainText(
      "6 of 12 Sample",
    );
    const volcano = page.getByTestId("eda-viz-volcano");
    await expect(volcano).toBeVisible();
    await expect(volcano.locator("canvas")).toBeVisible();
    await expect(page.getByTestId("eda-viz-volcano-selection")).toContainText(
      "1 gene selected",
    );

    await page.getByRole("button", { name: "Open in EDA tab" }).click();
    // The first request to the EDA route compiles it on a dev server.
    await expect(page).toHaveURL(
      new RegExp(`/plasmodb/conversation/${conversationId}/eda$`),
      { timeout: 60_000 },
    );
    await expect(page.getByTestId("eda-workbench-header")).toContainText(STUDY_TITLE);
    await expect(page.getByTestId(`eda-entity-${SAMPLE_ENTITY}`)).toContainText(
      "6 of 12",
    );
    await expect(
      page.getByTestId(`eda-filter-chip-${SAMPLE_ENTITY}-${TEMPERATURE_VAR}`),
    ).toContainText("febrile");
  });

  test("a filter added in the tab travels as bind then set-filters", async ({
    page,
    context,
  }) => {
    const conversationId = await openConversation(context);
    await routeEdaReads(page);
    const actions: string[] = [];
    await page.route(`**/api/v1/conversations/${conversationId}/eda`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill(json({ analysis: null, descriptor: null }));
        return;
      }
      const body = route.request().postDataJSON() as { action: string };
      actions.push(body.action);
      const analysis = body.action === "bind" ? analysisState() : FILTERED_ANALYSIS;
      await route.fulfill(json({ analysis, job: null, step: null }));
    });

    await page.goto(`/plasmodb/conversation/${conversationId}/eda`);
    await page.getByTestId("eda-study-search").fill("heat shock");
    await page.getByTestId(`eda-study-row-${DATASET_ID}`).click();
    await expect(page.getByTestId("eda-subset-cell")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId(`eda-entity-${SAMPLE_ENTITY}`)).toContainText(
      "12 of 12",
    );

    await page.getByTestId(`eda-variable-${TEMPERATURE_VAR}`).click();
    await page.getByRole("checkbox", { name: "febrile" }).check();
    await page.getByRole("button", { name: "Apply filter" }).click();

    await expect(page.getByTestId(`eda-entity-${SAMPLE_ENTITY}`)).toContainText(
      "6 of 12",
    );
    await expect(
      page.getByTestId(`eda-filter-chip-${SAMPLE_ENTITY}-${TEMPERATURE_VAR}`),
    ).toContainText("febrile");
    expect(actions).toEqual(["bind", "set-filters"]);
  });

  test("a completed compute exports a step the strategy rail lists", async ({
    page,
    context,
  }) => {
    const conversationId = await openConversation(context);
    await routeEdaReads(page);
    let exportBody: unknown = null;
    await page.route(`**/api/v1/conversations/${conversationId}/eda`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill(json({ analysis: null, descriptor: null }));
        return;
      }
      const body = route.request().postDataJSON() as { action: string };
      if (body.action === "run-compute") {
        await route.fulfill(
          json({
            analysis: analysisState({ revision: 1, numComputations: 1 }),
            job: {
              jobId: "db04204e5386396e1ca2cb78469ab6fb",
              taskId: null,
              appName: "differentialexpression",
              status: "complete",
            },
            step: null,
          }),
        );
        return;
      }
      if (body.action === "export-step") {
        exportBody = body;
        await route.fulfill(
          json({
            analysis: analysisState({ revision: 2, numComputations: 1 }),
            job: null,
            step: {
              id: conversationId,
              name: "Heat shock volcano",
              siteId: "plasmodb",
              recordType: "transcript",
              rootStepId: EXPORTED_STEP.id,
              isSaved: false,
              steps: [EXPORTED_STEP],
              createdAt: "2026-08-28T00:00:00Z",
              updatedAt: "2026-08-28T00:00:00Z",
            },
          }),
        );
        return;
      }
      await route.fulfill(json({ analysis: analysisState(), job: null, step: null }));
    });

    await page.goto(`/plasmodb/conversation/${conversationId}/eda`);
    await page.getByTestId("eda-study-search").fill("heat shock");
    await page.getByTestId(`eda-study-row-${DATASET_ID}`).click();
    await expect(page.getByTestId("eda-compute-cell")).toBeVisible({ timeout: 20_000 });

    await page.getByLabel("Comparator variable").selectOption(TEMPERATURE_VAR);
    await page.getByLabel("Group A").selectOption("normal");
    await page.getByLabel("Group B").selectOption("febrile");
    await page.getByRole("button", { name: "Run compute" }).click();

    const exportButton = page.getByRole("button", { name: "Export as step" });
    await expect(exportButton).toBeEnabled({ timeout: 20_000 });
    await exportButton.click();
    await expect
      .poll(() => (exportBody as { action?: string } | null)?.action)
      .toBe("export-step");

    // Client-side navigation back to the thread, which keeps the query cache
    // the export wrote the strategy into.
    await page.locator(`[data-conversation-id="${conversationId}"]`).click();
    await expect(page).toHaveURL(
      new RegExp(`/plasmodb/conversation/${conversationId}$`),
    );
    const panel = page.getByTestId("rail-strategy-panel");
    if (!(await panel.isVisible())) {
      await page.getByRole("button", { name: /^(Open|Close) Strategy$/ }).click();
    }
    await expect(panel).toBeVisible({ timeout: 20_000 });
    await expect(
      page.getByTestId(`compact-step-row-${EXPORTED_STEP.id}`),
    ).toContainText("EDA volcano");
  });
});
