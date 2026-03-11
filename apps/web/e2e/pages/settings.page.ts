import { type Page, expect } from "@playwright/test";

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
    // Settings modal has no close button — dismiss with Escape key.
    await this.page.keyboard.press("Escape");
    await expect(this.page.getByRole("dialog")).not.toBeVisible({ timeout: 5_000 });
  }

  async openTab(tabName: "General" | "Data" | "Advanced") {
    await this.page.getByRole("dialog").getByRole("button", { name: tabName }).click();
  }

  async expectTabVisible(tabName: "General" | "Data" | "Advanced") {
    await expect(
      this.page.getByRole("dialog").getByRole("button", { name: tabName }),
    ).toBeVisible();
  }

  async expectThreeTabsVisible() {
    for (const tab of ["General", "Data", "Advanced"] as const) {
      await this.expectTabVisible(tab);
    }
  }

  // ── Sync delete to WDK setting ──────────────────────────────────

  private get syncDeleteCheckbox() {
    return this.page.getByTestId("sync-delete-to-wdk-checkbox");
  }

  /** Enable the "Sync strategy deletion to WDK" setting. */
  async enableSyncDeleteToWdk() {
    await this.open();
    await this.openTab("Advanced");
    if (!(await this.syncDeleteCheckbox.isChecked())) {
      await this.syncDeleteCheckbox.check();
    }
    await this.close();
  }

  /** Disable the "Sync strategy deletion to WDK" setting. */
  async disableSyncDeleteToWdk() {
    await this.open();
    await this.openTab("Advanced");
    if (await this.syncDeleteCheckbox.isChecked()) {
      await this.syncDeleteCheckbox.uncheck();
    }
    await this.close();
  }
}
