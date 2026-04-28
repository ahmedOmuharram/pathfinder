import { expect } from "@playwright/test";
import { AxeBuilder } from "@axe-core/playwright";
import { test as baseTest } from "./test";

interface SeriousViolation {
  id: string;
  nodes: number;
  impact: string;
  help: string;
}

/**
 * Extends the project test fixture with an automatic accessibility audit
 * that runs after every test. Fails the test if any axe-core violation
 * with impact "serious" or "critical" is reported.
 *
 * Use this fixture instead of the base `test` for every journey and
 * cross-feature spec — the journeys exercise the breadth of the UI so
 * an a11y audit at end-of-test catches real regressions.
 */
export const test = baseTest.extend({
  page: async ({ page }, use, testInfo) => {
    await use(page);
    if (testInfo.status === "skipped") return;
    if (page.isClosed()) return;
    const result = await new AxeBuilder({ page }).analyze();
    const seriousAndCritical: SeriousViolation[] = result.violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map((v) => ({
        id: v.id,
        nodes: v.nodes.length,
        impact: v.impact ?? "",
        help: v.help,
      }));
    expect(
      seriousAndCritical,
      `Accessibility violations (serious/critical) found:\n${seriousAndCritical
        .map((v) => `  - [${v.impact}] ${v.id} (${v.nodes} nodes): ${v.help}`)
        .join("\n")}`,
    ).toEqual([]);
  },
});

export { expect } from "@playwright/test";
