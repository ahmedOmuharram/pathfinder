/**
 * Branching a thread that has an EDA study open.
 *
 * The binding, the analysis and its subset are the real service's: the tab
 * hydrates from `GET /conversations/{id}/eda`. A branch holds an analysis of
 * its own, so what it opens or filters never reaches its parent.
 */

import { test, expect } from "../../fixtures/test";
import { DATASET_ID, FEBRILE_FILTER, SITE_ID, STUDY_TITLE } from "../../fixtures/eda";
import { echoOf } from "./prompts";

const OPEN_TURN = "show me heat shock genes";
const FILTER_CHIP = `eda-filter-chip-${FEBRILE_FILTER.entityId}-${FEBRILE_FILTER.variableId}`;

interface AnalysisRead {
  analysis: {
    analysisId: string;
    studyDisplayName: string;
    numFilters: number;
  } | null;
}

test.describe("Branching a thread with a study open", () => {
  // Each journey drives three to five turns through the worker, and one queued
  // behind another suite's build waits minutes.
  test.describe.configure({ timeout: 600_000 });

  test("a branch opens its own analysis and leaves the parent's subset alone", async ({
    chatPage,
    sitePicker,
    apiClient,
    page,
  }) => {
    await chatPage.goto();
    await sitePicker.selectSite(SITE_ID);
    await chatPage.newChat(SITE_ID);

    await chatPage.sendTurn(OPEN_TURN, echoOf(OPEN_TURN));
    const parentId = chatPage.lastStrategyId as string;

    // Open a study on the thread and narrow its subset.
    const bound = await apiClient.patch(`/api/v1/conversations/${parentId}/eda`, {
      data: { action: "bind", siteId: SITE_ID, datasetId: DATASET_ID },
    });
    expect(bound.ok(), `bind ${bound.status()}: ${await bound.text()}`).toBeTruthy();
    const parentBound = (await bound.json()) as AnalysisRead;
    const parentAnalysisId = parentBound.analysis?.analysisId ?? "";
    expect(parentAnalysisId).not.toBe("");
    expect(parentBound.analysis?.studyDisplayName).toBe(STUDY_TITLE);

    const filtered = await apiClient.patch(`/api/v1/conversations/${parentId}/eda`, {
      data: { action: "set-filters", filters: [FEBRILE_FILTER] },
    });
    expect(
      filtered.ok(),
      `set-filters ${filtered.status()}: ${await filtered.text()}`,
    ).toBeTruthy();
    expect(((await filtered.json()) as AnalysisRead).analysis?.numFilters).toBe(1);

    // The parent's tab renders the study and its filter.
    await page.goto(`/${SITE_ID}/conversation/${parentId}/eda`);
    await expect(page.getByTestId("eda-workbench-title")).toContainText(STUDY_TITLE, {
      timeout: 60_000,
    });
    await expect(page.getByTestId(FILTER_CHIP)).toBeVisible({ timeout: 60_000 });

    // Branch from the thread.
    await page.goto(`/${SITE_ID}/conversation/${parentId}`);
    await expect(chatPage.composer).toBeVisible({ timeout: 60_000 });
    const branchId = await chatPage.branchFromAssistantReply(echoOf(OPEN_TURN));
    expect(branchId).not.toBe(parentId);

    // The branch opens the same study on an analysis of its own.
    const branchBound = await apiClient.patch(`/api/v1/conversations/${branchId}/eda`, {
      data: { action: "bind", siteId: SITE_ID, datasetId: DATASET_ID },
    });
    expect(
      branchBound.ok(),
      `branch bind ${branchBound.status()}: ${await branchBound.text()}`,
    ).toBeTruthy();
    const branchAnalysis = ((await branchBound.json()) as AnalysisRead).analysis;
    expect(branchAnalysis?.studyDisplayName).toBe(STUDY_TITLE);
    expect(branchAnalysis?.numFilters).toBe(0);
    expect(branchAnalysis?.analysisId).not.toBe(parentAnalysisId);

    // The branch's own study card renders, with no filter of the parent's.
    await page.goto(`/${SITE_ID}/conversation/${branchId}/eda`);
    await expect(page.getByTestId("eda-workbench-title")).toContainText(STUDY_TITLE, {
      timeout: 60_000,
    });
    await expect(page.getByTestId(FILTER_CHIP)).toHaveCount(0);

    // The parent is untouched, on the wire and on the tab.
    const parentAfter = await apiClient.get(`/api/v1/conversations/${parentId}/eda`);
    const parentState = ((await parentAfter.json()) as AnalysisRead).analysis;
    expect(parentState?.analysisId).toBe(parentAnalysisId);
    expect(parentState?.numFilters).toBe(1);

    await page.goto(`/${SITE_ID}/conversation/${parentId}/eda`);
    await expect(page.getByTestId("eda-workbench-title")).toContainText(STUDY_TITLE, {
      timeout: 60_000,
    });
    await expect(page.getByTestId(FILTER_CHIP)).toBeVisible({ timeout: 60_000 });
  });
});
