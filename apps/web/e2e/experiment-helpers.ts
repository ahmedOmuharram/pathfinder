import { type Page } from "@playwright/test";
import { setupAuth } from "./helpers";

/**
 * Navigate to the experiments tab with authentication.
 */
export async function gotoExperiments(page: Page): Promise<void> {
  await setupAuth(page);
  await page.goto("/experiments");
}

/**
 * Start a new experiment by clicking the "New Experiment" button
 * and selecting the specified mode.
 */
export async function startNewExperiment(
  page: Page,
  mode: "single" | "multistep" | "import" = "multistep",
): Promise<void> {
  // Click the new experiment button (use .first() as both the empty state and
  // the header may render a "New Experiment" button simultaneously).
  await page
    .getByRole("button", { name: /new experiment/i })
    .first()
    .click();
  // Select mode - look for mode-specific button or option
  if (mode === "single") {
    await page.getByTestId("mode-single").click();
  } else if (mode === "multistep") {
    await page.getByTestId("mode-multistep").click();
  } else {
    await page.getByTestId("mode-import").click();
  }
}

/**
 * Mock the experiment list API endpoint.
 */
export async function mockExperimentList(
  page: Page,
  experiments: object[],
): Promise<void> {
  await page.route("**/api/v1/experiments", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(experiments),
      });
    } else {
      await route.continue();
    }
  });
}

/**
 * Mock the SSE stream for experiment execution.
 * Sends the provided events as SSE frames, followed by experiment_end.
 */
export async function mockExperimentSSE(
  page: Page,
  events: Array<{ type: string; data: object }>,
): Promise<void> {
  await page.route("**/api/v1/experiments", async (route) => {
    if (route.request().method() === "POST") {
      const sseBody = events
        .map((e) => `event: ${e.type}\ndata: ${JSON.stringify(e.data)}\n\n`)
        .join("");
      const endFrame = `event: experiment_end\ndata: {}\n\n`;

      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: {
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
        body: sseBody + endFrame,
      });
    } else {
      await route.continue();
    }
  });
}

// Re-export types for convenience
export type MockExperiment = {
  id: string;
  status: string;
  name: string;
  config: {
    siteId: string;
    recordType: string;
    searchName: string;
    mode: string;
  };
};

/**
 * Create a minimal mock experiment object for use with mockExperimentList.
 */
export function createMockExperiment(
  overrides: Partial<MockExperiment> = {},
): MockExperiment {
  return {
    id: `exp_${Date.now()}`,
    status: "completed",
    name: "Test Experiment",
    config: {
      siteId: "PlasmoDB",
      recordType: "gene",
      searchName: "GenesByTaxon",
      mode: "multi-step",
    },
    ...overrides,
  };
}
