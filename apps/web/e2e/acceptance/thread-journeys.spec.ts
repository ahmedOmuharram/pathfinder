/**
 * Thread acceptance journey. Frozen; implementers may not edit this file.
 *
 * It runs only when THREAD_ACCEPTANCE is set:
 *   THREAD_ACCEPTANCE=1 npx playwright test --project=thread-acceptance
 *
 * One route-mocked turn carries the whole redesign: a seven row trace with a
 * summary per call, a task row, an approval card, a volcano figure, and no
 * JSON anywhere. Every frame goes through `sseFrame` / `sseDone`, so the
 * client never rejects a hand-written frame. The chunk sequence is the one
 * recorded in `src/acceptance/thread/recordedTurn.json`, inlined here because
 * an acceptance module carries its own fixtures.
 */

import { test, expect, BASE_URL } from "../fixtures/test";
import { sseDone, sseFrame, uiMessageStreamHeaders } from "../fixtures/sse";
import { CSRF_HEADERS } from "../fixtures/api-client";
import type { BrowserContext, Page } from "@playwright/test";

test.skip(
  () => process.env["THREAD_ACCEPTANCE"] !== "1",
  "Thread acceptance journeys run explicitly, at batch 2 close",
);

const MESSAGE_ID = "11111111-1111-1111-1111-111111111111";
const TASK_ID = "00000000-0000-0000-0000-0000000000aa";
const DATASET = "DS_e973eadd57";

const SAMPLE = {
  entityId: "ENT_8151325d",
  entityDisplayName: "Sample",
  count: 6,
  unfilteredCount: 12,
};
const READS = {
  entityId: "ENT_fd574cd6",
  entityDisplayName: "pfal3D7 htseq counts",
  count: 34320,
  unfilteredCount: 68640,
};

const ANALYSIS_STATE = {
  siteId: "plasmodb",
  datasetId: DATASET,
  studyId: "STUDY_e973eadd57",
  analysisId: "a-1",
  revision: 3,
  numFilters: 2,
  numComputations: 1,
  canExportRows: true,
  studyDisplayName: "Heat shock response in sensitive mutants (LRR5, DHC)",
  displayName: "Febrile samples",
  filters: [
    {
      entityId: "ENT_8151325d",
      variableId: "VAR_081ab087",
      type: "stringSet",
      stringSet: ["febrile"],
    },
    {
      entityId: "ENT_8151325d",
      variableId: "VAR_7033e90f",
      type: "numberRange",
      min: 37,
      max: 42,
    },
  ],
  filterSummaries: ["temperature_condition is febrile", "Temperature is 37 to 42"],
  entityCounts: [SAMPLE, READS],
};

const SUBSET_PREVIEW = {
  datasetId: DATASET,
  analysisId: "a-1",
  entityCounts: [SAMPLE],
  distributionNote: null,
  distribution: {
    variableId: "VAR_7033e90f",
    variableDisplayName: "Temperature",
    labels: ["[37, 38)", "[41, 42]"],
    values: [6, 6],
    subsetSize: 6,
    numVarValues: 6,
    numMissingCases: 0,
    isMultiValued: false,
  },
};

const VOLCANO = {
  datasetId: DATASET,
  analysisId: "a-1",
  chart: "volcano",
  effectSizeLabel: "log2(Fold Change)",
  effectSizeThreshold: 1,
  significanceThreshold: 0.05,
  effectDirection: "upAndDown",
  totalPoints: 5511,
  retainedPoints: 1543,
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

const SUB_AGENT = {
  toolCallId: "sa_1",
  subAgent: "frame_problem",
  phase: "frame",
  modelId: "openai:gpt-5.6-luna",
  summary: "frame the heat shock question",
};

const CHUNKS: unknown[] = [
  {
    type: "start",
    messageId: MESSAGE_ID,
    messageMetadata: {
      phase: "lead",
      model: "mock:deterministic",
      traceId: "thread-acceptance-1",
      createdAt: "2026-08-29T00:00:00.000Z",
    },
  },
  { type: "data-turn-status", data: { label: "Thinking...", waitingOnLlm: true } },
  { type: "text-start", id: "t1" },
  {
    type: "text-delta",
    id: "t1",
    delta: "I looked at the heat shock study and subset it to the febrile samples.",
  },
  { type: "text-end", id: "t1" },
  { type: "tool-input-start", toolCallId: "call_1", toolName: "search_eda_studies" },
  {
    type: "tool-input-available",
    toolCallId: "call_1",
    toolName: "search_eda_studies",
    input: { query: "heat shock", limit: 5 },
  },
  { type: "tool-output-available", toolCallId: "call_1", output: { studies: 3 } },
  {
    type: "data-tool-summary",
    data: {
      toolCallId: "call_1",
      summary: "3 studies matched heat shock",
      status: "ok",
    },
  },
  { type: "tool-input-start", toolCallId: "call_2", toolName: "open_eda_analysis" },
  {
    type: "tool-input-available",
    toolCallId: "call_2",
    toolName: "open_eda_analysis",
    input: { datasetId: DATASET, purpose: "subset the febrile samples" },
  },
  {
    type: "tool-output-available",
    toolCallId: "call_2",
    output: { analysisId: "a-1" },
  },
  { type: "data-eda.analysis-state", data: ANALYSIS_STATE },
  {
    type: "data-tool-summary",
    data: {
      toolCallId: "call_2",
      summary: "Opened Febrile samples on DS_e973eadd57",
      status: "ok",
    },
  },
  { type: "data-sub-agent-call", id: "sa_1", data: { ...SUB_AGENT, state: "started" } },
  {
    type: "data-sub-agent-step",
    data: {
      parentToolCallId: "sa_1",
      kind: "tool",
      state: "started",
      toolCallId: "s1",
      toolName: "search_for_searches",
      args: { query: "heat shock" },
    },
  },
  {
    type: "data-sub-agent-step",
    data: {
      parentToolCallId: "sa_1",
      kind: "tool",
      state: "completed",
      toolCallId: "s1",
      resultSummary: "12 searches",
    },
  },
  {
    type: "data-sub-agent-step",
    data: {
      parentToolCallId: "sa_1",
      kind: "tool",
      state: "started",
      toolCallId: "s2",
      toolName: "set_criterion",
      args: { criterionId: "c1", searchName: "GenesByText" },
    },
  },
  {
    type: "data-sub-agent-step",
    data: {
      parentToolCallId: "sa_1",
      kind: "tool",
      state: "completed",
      toolCallId: "s2",
      resultSummary: "c1 set to GenesByText",
    },
  },
  {
    type: "data-sub-agent-call",
    id: "sa_1",
    data: {
      ...SUB_AGENT,
      state: "completed",
      succeeded: true,
      tokens: 12300,
      costUsd: "0.004",
    },
  },
  { type: "tool-input-start", toolCallId: "call_3", toolName: "preview_eda_subset" },
  {
    type: "tool-input-available",
    toolCallId: "call_3",
    toolName: "preview_eda_subset",
    input: { entityId: "ENT_8151325d", distributionVariableId: "VAR_7033e90f" },
  },
  {
    type: "tool-output-available",
    toolCallId: "call_3",
    output: { entityCounts: [SAMPLE] },
  },
  { type: "data-eda.subset-preview", data: SUBSET_PREVIEW },
  {
    type: "data-tool-summary",
    data: { toolCallId: "call_3", summary: "6 of 12 Sample", status: "ok" },
  },
  {
    type: "tool-input-start",
    toolCallId: "call_4",
    toolName: "run_control_tests_on_step",
  },
  {
    type: "tool-input-available",
    toolCallId: "call_4",
    toolName: "run_control_tests_on_step",
    input: { wdkStepId: 132 },
  },
  {
    type: "data-background-task-started",
    data: {
      taskId: TASK_ID,
      toolName: "run_control_tests_on_step",
      estimatedDurationSeconds: 3,
    },
  },
  {
    type: "data-task-progress",
    id: TASK_ID,
    data: { taskId: TASK_ID, percent: 0.66, message: "Comparing controls" },
  },
  { type: "data-task-completed", data: { taskId: TASK_ID, status: "success" } },
  {
    type: "tool-output-available",
    toolCallId: "call_4",
    output: { recovered: 8, total: 10 },
  },
  {
    type: "data-tool-summary",
    data: {
      toolCallId: "call_4",
      summary: "8 of 10 positive controls recovered",
      status: "ok",
    },
  },
  {
    type: "tool-input-start",
    toolCallId: "call_5",
    toolName: "optimize_search_parameters",
  },
  {
    type: "tool-input-available",
    toolCallId: "call_5",
    toolName: "optimize_search_parameters",
    input: { target: { wdkStepId: 132 }, controls: { setId: "ctrl_1" } },
  },
  { type: "tool-approval-request", toolCallId: "call_5", approvalId: "call_5" },
  { type: "data-eda.viz", data: VOLCANO },
  { type: "text-start", id: "t2" },
  {
    type: "text-delta",
    id: "t2",
    delta: "Approve the parameter sweep and I will run it.",
  },
  { type: "text-end", id: "t2" },
  {
    type: "data-lead-usage",
    id: "lu_1",
    data: { modelId: "openai:gpt-5.6-luna", tokens: 41800, costUsd: "0.0131" },
  },
  { type: "finish", finishReason: "stop" },
];

const ROW_LABELS = [
  "Find studies",
  "Open study",
  "Find searches",
  "Choose a search",
  "Preview samples",
  "Run control tests",
  "Optimize parameters",
];

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

test.describe("Thread acceptance journey", () => {
  test("one turn draws a quiet trace, a task row, an approval card and a figure", async ({
    page,
    context,
  }) => {
    const conversationId = await openConversation(context);
    await page.route(`**/api/v1/conversations/${conversationId}/eda`, (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ analysis: null, descriptor: null }),
      }),
    );
    const stream = [...CHUNKS.map((chunk) => sseFrame(chunk)), sseDone()].join("");
    await page.route("**/api/v1/chat", (route) =>
      route.fulfill({ status: 200, headers: uiMessageStreamHeaders(), body: stream }),
    );

    await page.goto(`/plasmodb/conversation/${conversationId}`);
    await sendTurn(page, "explore the heat shock study");

    // The run that holds the rows; the other run of this turn holds none.
    const trace = page.locator(
      '[data-testid="turn-trace"]:has([data-testid="trace-row"])',
    );
    await expect(trace).toHaveCount(1, { timeout: 30_000 });
    await expect(trace.getByTestId("turn-trace-summary")).toHaveText("Waiting for you");

    const rows = trace.getByTestId("trace-row");
    await expect(rows).toHaveCount(7);
    await expect(rows).toContainText(ROW_LABELS);
    const firstRow = trace.locator(
      '[data-testid="trace-row"]:has-text("Find studies")',
    );
    await expect(firstRow).toContainText("3 studies matched heat shock");

    // The assertion the whole redesign turns on: no raw call JSON in the page.
    await expect(page.locator("body")).not.toContainText("wdkStepId");
    await expect(page.locator("body")).not.toContainText("distributionVariableId");

    await expect(page.getByTestId("task-row")).toContainText("Completed");

    await expect(page.getByTestId("approval-card")).toBeVisible();
    await expect(page.getByTestId("tool-approval-approve")).toBeEnabled();

    await expect(page.getByTestId("eda-viz-volcano")).toBeVisible();

    // The toggle flips the rows, and a second click puts them back.
    const shownFirst = await firstRow.isVisible();
    const toggle = trace.getByTestId("turn-trace-toggle");
    await toggle.click();
    if (shownFirst) {
      await expect(firstRow).toBeHidden();
    } else {
      await expect(firstRow).toBeVisible();
    }
    await toggle.click();
    if (shownFirst) {
      await expect(firstRow).toBeVisible();
    } else {
      await expect(firstRow).toBeHidden();
    }
  });
});
