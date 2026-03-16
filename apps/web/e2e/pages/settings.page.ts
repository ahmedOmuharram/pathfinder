import { type Page, expect } from "@playwright/test";

type SettingsTab = "Model" | "Data" | "Advanced" | "Seeding";

export class SettingsPage {
  constructor(private page: Page) {}

  /** Open settings via the top bar settings button. */
  async open() {
    await this.page.getByRole("button", { name: /settings/i }).click();
    await expect(
      this.page.getByRole("dialog").filter({ hasText: /settings/i }),
    ).toBeVisible();
  }

  async close() {
    // Settings modal has a close button in the header now.
    await this.page.keyboard.press("Escape");
    await expect(this.page.getByRole("dialog")).not.toBeVisible({ timeout: 5_000 });
  }

  async openTab(tabName: SettingsTab) {
    await this.page
      .getByRole("dialog")
      .getByRole("button", { name: tabName, exact: true })
      .click();
  }

  async expectTabVisible(tabName: SettingsTab) {
    await expect(
      this.page.getByRole("dialog").getByRole("button", { name: tabName, exact: true }),
    ).toBeVisible();
  }

  async expectAllTabsVisible() {
    for (const tab of ["Model", "Data", "Advanced", "Seeding"] as const) {
      await this.expectTabVisible(tab);
    }
  }
}
